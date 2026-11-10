#include "city_database.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#include "esp_log.h"
#include "esp_partition.h"

#define CITY_DB_MAGIC 0x32424443UL /* CDB2 */
#define CITY_DB_HEADER_SIZE 12U
#define CITY_DB_ALIAS_MAX 192

static const char *TAG = "CITY_DB";

typedef struct {
    char name[CITY_DB_NAME_MAX];
    char country[CITY_DB_COUNTRY_MAX];
    char timezone[CITY_DB_TZ_MAX];
    char aliases[CITY_DB_ALIAS_MAX];
} city_db_full_record_t;

static const esp_partition_t *partition = NULL;
static uint32_t record_count = 0;
static uint32_t data_offset = 0;
static uint32_t index_size = 0;

/* Keep the large index in flash. Only one small window is cached in RAM. */
#define CITY_DB_INDEX_CACHE_SIZE 4096U
#define CITY_DB_RECORD_RAW_MAX (sizeof(uint8_t[4]) + (CITY_DB_NAME_MAX - 1) + (CITY_DB_COUNTRY_MAX - 1) + (CITY_DB_TZ_MAX - 1) + (CITY_DB_ALIAS_MAX - 1))
static uint8_t index_cache[CITY_DB_INDEX_CACHE_SIZE];
static uint32_t index_cache_base = UINT32_MAX;
static uint32_t index_cache_valid = 0;

static bool read_bytes(uint32_t offset, void *buffer, size_t size)
{
    return partition != NULL && esp_partition_read(partition, offset, buffer, size) == ESP_OK;
}

static bool read_record_offset(uint32_t index, uint32_t *offset)
{
    if (partition == NULL || offset == NULL || index >= record_count) return false;

    uint32_t byte_offset = CITY_DB_HEADER_SIZE + index * sizeof(uint32_t);
    uint32_t cache_base = (byte_offset / CITY_DB_INDEX_CACHE_SIZE) * CITY_DB_INDEX_CACHE_SIZE;

    if (cache_base != index_cache_base) {
        uint32_t index_end = CITY_DB_HEADER_SIZE + index_size;
        if (cache_base >= index_end || cache_base >= partition->size) return false;

        uint32_t bytes_to_read = index_end - cache_base;
        if (bytes_to_read > CITY_DB_INDEX_CACHE_SIZE) {
            bytes_to_read = CITY_DB_INDEX_CACHE_SIZE;
        }
        if (!read_bytes(cache_base, index_cache, bytes_to_read)) return false;

        index_cache_base = cache_base;
        index_cache_valid = bytes_to_read;
    }

    uint32_t relative = byte_offset - index_cache_base;
    if (relative + sizeof(uint32_t) > index_cache_valid) return false;

    memcpy(offset, index_cache + relative, sizeof(uint32_t));
    return true;
}

static bool read_record_raw(uint32_t index, uint8_t *raw, size_t raw_size, size_t *record_size)
{
    if (raw == NULL || record_size == NULL || raw_size < sizeof(uint8_t[4])) return false;

    uint32_t offset = 0;
    if (!read_record_offset(index, &offset) || offset < data_offset ||
        offset > partition->size - sizeof(uint8_t[4])) {
        return false;
    }

    /* One flash read per record keeps a full database search responsive. */
    if (offset <= partition->size - CITY_DB_RECORD_RAW_MAX) {
        if (!read_bytes(offset, raw, CITY_DB_RECORD_RAW_MAX)) return false;
    } else {
        if (!read_bytes(offset, raw, sizeof(uint8_t[4]))) return false;
        uint32_t payload_size = sizeof(uint8_t[4]) + raw[0] + raw[1] + raw[2] + raw[3];
        if (payload_size > raw_size || payload_size > partition->size - offset) return false;
        if (!read_bytes(offset + sizeof(uint8_t[4]), raw + sizeof(uint8_t[4]), payload_size - sizeof(uint8_t[4]))) {
            return false;
        }
    }

    if (raw[0] >= CITY_DB_NAME_MAX || raw[1] >= CITY_DB_COUNTRY_MAX ||
        raw[2] >= CITY_DB_TZ_MAX || raw[3] >= CITY_DB_ALIAS_MAX) {
        return false;
    }
    *record_size = sizeof(uint8_t[4]) + raw[0] + raw[1] + raw[2] + raw[3];
    return *record_size <= raw_size;
}

static bool decode_raw_record(const uint8_t *raw, size_t record_size, city_db_full_record_t *record)
{
    if (raw == NULL || record == NULL || record_size < sizeof(uint8_t[4])) return false;
    if (raw[0] >= CITY_DB_NAME_MAX || raw[1] >= CITY_DB_COUNTRY_MAX ||
        raw[2] >= CITY_DB_TZ_MAX || raw[3] >= CITY_DB_ALIAS_MAX) return false;

    size_t expected = sizeof(uint8_t[4]) + raw[0] + raw[1] + raw[2] + raw[3];
    if (expected > record_size) return false;

    memset(record, 0, sizeof(*record));
    size_t cursor = sizeof(uint8_t[4]);
    memcpy(record->name, raw + cursor, raw[0]);
    cursor += raw[0];
    memcpy(record->country, raw + cursor, raw[1]);
    cursor += raw[1];
    memcpy(record->timezone, raw + cursor, raw[2]);
    cursor += raw[2];
    memcpy(record->aliases, raw + cursor, raw[3]);
    return true;
}

static uint32_t utf8_next(const unsigned char **cursor)
{
    const unsigned char *p = *cursor;
    uint32_t value = *p++;
    if (value < 0x80) {
        *cursor = p;
        return value;
    }
    if ((value & 0xE0) == 0xC0 && (p[0] & 0xC0) == 0x80) {
        value = ((value & 0x1F) << 6) | (p[0] & 0x3F);
        p += 1;
    } else if ((value & 0xF0) == 0xE0 && (p[0] & 0xC0) == 0x80 && (p[1] & 0xC0) == 0x80) {
        value = ((value & 0x0F) << 12) | ((p[0] & 0x3F) << 6) | (p[1] & 0x3F);
        p += 2;
    } else if ((value & 0xF8) == 0xF0 && (p[0] & 0xC0) == 0x80 &&
               (p[1] & 0xC0) == 0x80 && (p[2] & 0xC0) == 0x80) {
        value = ((value & 0x07) << 18) | ((p[0] & 0x3F) << 12) |
                ((p[1] & 0x3F) << 6) | (p[2] & 0x3F);
        p += 3;
    }
    *cursor = p;
    return value;
}

static uint32_t unicode_lower(uint32_t value)
{
    if (value >= 'A' && value <= 'Z') return value + ('a' - 'A');
    if (value >= 0x0410 && value <= 0x042F) return value + 0x20; /* Cyrillic А–Я */
    if (value == 0x0401) return 0x0451; /* Ё */
    return value;
}

static bool text_contains(const char *text, const char *query)
{
    if (text == NULL || query == NULL || query[0] == '\0') return false;

    const unsigned char *start = (const unsigned char *)text;
    while (*start != '\0') {
        const unsigned char *text_cursor = start;
        const unsigned char *query_cursor = (const unsigned char *)query;
        while (*query_cursor != '\0') {
            uint32_t text_value = unicode_lower(utf8_next(&text_cursor));
            uint32_t query_value = unicode_lower(utf8_next(&query_cursor));
            if (text_value != query_value) break;
        }
        if (*query_cursor == '\0') return true;
        utf8_next(&start);
    }
    return false;
}

#define CITY_DB_SCAN_CACHE_SIZE 4096U

typedef struct {
    uint8_t *buffer;
    uint32_t position;
    size_t cursor;
    size_t valid;
} city_db_stream_t;

static bool stream_fill(city_db_stream_t *stream)
{
    if (stream == NULL || stream->buffer == NULL || stream->position >= partition->size) {
        return false;
    }

    uint32_t remaining = partition->size - stream->position;
    size_t amount = remaining < CITY_DB_SCAN_CACHE_SIZE
        ? (size_t)remaining : CITY_DB_SCAN_CACHE_SIZE;
    if (!read_bytes(stream->position, stream->buffer, amount)) return false;

    stream->position += (uint32_t)amount;
    stream->cursor = 0;
    stream->valid = amount;
    return true;
}

static bool stream_read(city_db_stream_t *stream, void *destination, size_t size)
{
    uint8_t *out = destination;
    while (size > 0) {
        if (stream->cursor >= stream->valid && !stream_fill(stream)) return false;
        size_t available = stream->valid - stream->cursor;
        size_t amount = size < available ? size : available;
        memcpy(out, stream->buffer + stream->cursor, amount);
        stream->cursor += amount;
        out += amount;
        size -= amount;
    }
    return true;
}

bool city_database_init(void)
{
    partition = esp_partition_find_first(
        ESP_PARTITION_TYPE_DATA,
        ESP_PARTITION_SUBTYPE_ANY,
        "cities");
    if (partition == NULL) {
        ESP_LOGW(TAG, "Cities partition not found; built-in cities remain available");
        return false;
    }
    ESP_LOGI(TAG, "Cities partition found: offset=0x%lx size=0x%lx",
             (unsigned long)partition->address,
             (unsigned long)partition->size);

    uint32_t header[3] = {0};
    if (!read_bytes(0, header, sizeof(header)) || header[0] != CITY_DB_MAGIC) {
        ESP_LOGE(TAG, "Invalid cities database header; expected CDB2");
        partition = NULL;
        return false;
    }

    record_count = header[1];
    /* The generated file stores the offset index immediately after the
     * 12-byte header. header[2] is the beginning of the record area. */
    data_offset = header[2];
    index_size = record_count * sizeof(uint32_t);
    index_cache_base = UINT32_MAX;
    index_cache_valid = 0;

    if (record_count == 0 || record_count > 100000 ||
        data_offset < CITY_DB_HEADER_SIZE + index_size ||
        data_offset > partition->size ||
        CITY_DB_HEADER_SIZE + index_size > partition->size) {
        ESP_LOGE(TAG, "Invalid cities database size: records=%lu data=0x%lx partition=0x%lx",
                 (unsigned long)record_count,
                 (unsigned long)data_offset,
                 (unsigned long)partition->size);
        record_count = 0;
        index_size = 0;
        partition = NULL;
        return false;
    }

    /* Read one index entry now. This validates the flash read without
     * allocating the complete index in internal RAM. */
    uint32_t first_offset = 0;
    if (!read_record_offset(0, &first_offset) ||
        first_offset < data_offset ||
        first_offset > partition->size - sizeof(uint8_t[4])) {
        ESP_LOGE(TAG, "Cannot read cities index from flash");
        record_count = 0;
        index_size = 0;
        partition = NULL;
        return false;
    }

    ESP_LOGI(TAG, "Cities database loaded: %lu records", (unsigned long)record_count);
    return true;
}

uint32_t city_database_count(void)
{
    return record_count;
}

bool city_database_get(uint32_t index, city_db_record_t *record)
{
    if (record == NULL || partition == NULL || index >= record_count) {
        return false;
    }

    uint8_t raw[CITY_DB_RECORD_RAW_MAX];
    size_t record_size = 0;
    if (!read_record_raw(index, raw, sizeof(raw), &record_size)) return false;

    city_db_full_record_t full;
    if (!decode_raw_record(raw, record_size, &full)) return false;
    memcpy(record->name, full.name, sizeof(record->name));
    memcpy(record->country, full.country, sizeof(record->country));
    memcpy(record->timezone, full.timezone, sizeof(record->timezone));
    return true;
}

static bool alias_is_ascii(const char *text, size_t length)
{
    for (size_t i = 0; i < length; i++) {
        if ((unsigned char)text[i] < 0x20 || (unsigned char)text[i] >= 0x7F) return false;
    }
    return true;
}

static bool alias_has_cyrillic(const char *text, size_t length)
{
    for (size_t i = 0; i + 1 < length; i++) {
        if ((unsigned char)text[i] == 0xD0 || (unsigned char)text[i] == 0xD1) return true;
    }
    return false;
}

static bool alias_has_han(const char *text, size_t length)
{
    for (size_t i = 0; i < length; i++) {
        if ((unsigned char)text[i] >= 0xE4 && (unsigned char)text[i] <= 0xE9) return true;
    }
    return false;
}

bool city_database_get_localized(uint32_t index, const char *language, city_db_record_t *record)
{
    if (record == NULL || partition == NULL || index >= record_count) return false;

    uint8_t raw[CITY_DB_RECORD_RAW_MAX];
    size_t record_size = 0;
    if (!read_record_raw(index, raw, sizeof(raw), &record_size)) return false;
    city_db_full_record_t full;
    if (!decode_raw_record(raw, record_size, &full)) return false;

    memcpy(record->name, full.name, sizeof(record->name));
    memcpy(record->country, full.country, sizeof(record->country));
    memcpy(record->timezone, full.timezone, sizeof(record->timezone));

    const bool want_ru = language && strcmp(language, "ru") == 0;
    const bool want_en = language && strcmp(language, "en") == 0;
    const bool want_zh = language && strcmp(language, "zh") == 0;
    if (want_en && alias_is_ascii(full.name, strlen(full.name))) return true;
    const char *cursor = full.aliases;
    while (*cursor) {
        const char *end = strchr(cursor, '|');
        size_t length = end ? (size_t)(end - cursor) : strlen(cursor);
        bool matches = false;
        if (want_ru) matches = alias_has_cyrillic(cursor, length);
        else if (want_en) matches = alias_is_ascii(cursor, length);
        else if (want_zh) matches = alias_has_han(cursor, length);
        else matches = alias_is_ascii(cursor, length) && !alias_is_ascii(full.name, strlen(full.name));
        if (matches && length > 0 && length < CITY_DB_NAME_MAX) {
            memcpy(record->name, cursor, length);
            record->name[length] = '\0';
            break;
        }
        if (!end) break;
        cursor = end + 1;
    }
    return true;
}

uint32_t city_database_search(const char *query,
                              uint32_t limit,
                              city_db_record_t *records,
                              uint32_t *indexes)
{
    if (partition == NULL || records == NULL || indexes == NULL ||
        limit == 0 || query == NULL || query[0] == '\0') return 0;

    city_db_stream_t stream = {
        .buffer = malloc(CITY_DB_SCAN_CACHE_SIZE),
        .position = data_offset,
        .cursor = 0,
        .valid = 0
    };
    if (stream.buffer == NULL) return 0;

    uint32_t found = 0;
    uint8_t raw[CITY_DB_RECORD_RAW_MAX];
    city_db_full_record_t item;

    for (uint32_t i = 0; i < record_count && found < limit; i++) {
        uint8_t lengths[4] = {0};
        if (!stream_read(&stream, lengths, sizeof(lengths))) break;

        size_t record_size = sizeof(lengths) + lengths[0] + lengths[1] + lengths[2] + lengths[3];
        if (lengths[0] >= CITY_DB_NAME_MAX || lengths[1] >= CITY_DB_COUNTRY_MAX ||
            lengths[2] >= CITY_DB_TZ_MAX || lengths[3] >= CITY_DB_ALIAS_MAX ||
            record_size > sizeof(raw)) {
            break;
        }

        memcpy(raw, lengths, sizeof(lengths));
        if (!stream_read(&stream, raw + sizeof(lengths), record_size - sizeof(lengths))) break;
        if (!decode_raw_record(raw, record_size, &item)) break;

        if (!text_contains(item.name, query) &&
            !text_contains(item.country, query) &&
            !text_contains(item.timezone, query) &&
            !text_contains(item.aliases, query)) {
            continue;
        }
        memcpy(records[found].name, item.name, sizeof(records[found].name));
        memcpy(records[found].country, item.country, sizeof(records[found].country));
        memcpy(records[found].timezone, item.timezone, sizeof(records[found].timezone));
        indexes[found] = i;
        found++;
    }

    free(stream.buffer);
    return found;
}
