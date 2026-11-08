#include "city_database.h"

#include <ctype.h>
#include <string.h>

// Compact built-in database. It resides in flash and requires no heap allocation.
static const city_db_record_t database[] = {
    {"Курск", "Россия", "MSK-3"},
    {"Киров", "Россия", "MSK-3"},
    {"Великий Новгород", "Россия", "MSK-3"},
    {"Нижний Новгород", "Россия", "MSK-3"},
    {"Южно-Сахалинск", "Россия", "SRET-11"},
    {"Москва", "Россия", "MSK-3"},
    {"Санкт-Петербург", "Россия", "MSK-3"},
    {"Владивосток", "Россия", "VLAT-10"},
    {"Екатеринбург", "Россия", "YEKT-5"},
    {"Новосибирск", "Россия", "NOVT-7"},
    {"Калининград", "Россия", "EET-2"},
    {"London", "United Kingdom", "GMT0BST,M3.5.0/1,M10.5.0/2"},
    {"Paris", "France", "CET-1CEST,M3.5.0,M10.5.0"},
    {"Berlin", "Deutschland", "CET-1CEST,M3.5.0,M10.5.0"},
    {"İstanbul", "Türkiye", "TRT-3"},
    {"New York", "United States", "EST5EDT,M3.2.0,M11.1.0"},
    {"Chicago", "United States", "CST6CDT,M3.2.0,M11.1.0"},
    {"Los Angeles", "United States", "PST8PDT,M3.2.0,M11.1.0"},
    {"San Jose", "United States", "PST8PDT,M3.2.0,M11.1.0"},
    {"Toronto", "Canada", "EST5EDT,M3.2.0,M11.1.0"},
    {"São Paulo", "Brasil", "BRT3"},
    {"Buenos Aires", "Argentina", "ART3"},
    {"Reykjavík", "Ísland", "UTC0"},
    {"Dubai", "United Arab Emirates", "GST-4"},
    {"Delhi", "India", "IST-5:30"},
    {"Bangkok", "Thailand", "ICT-7"},
    {"Singapore", "Singapore", "SGT-8"},
    {"Beijing", "China", "CST-8"},
    {"Tokyo", "Japan", "JST-9"},
    {"Seoul", "South Korea", "KST-9"},
    {"Sydney", "Australia", "AEST-10AEDT,M10.1.0,M4.1.0/3"},
    {"Auckland", "New Zealand", "NZST-12NZDT,M9.5.0,M4.1.0/3"},
    {"Santiago", "Chile", "CLT3CLST,M9.1.6,M4.1.6"},
    {"UTC", "UTC", "UTC0"},
};

#define DATABASE_COUNT (sizeof(database) / sizeof(database[0]))

static bool ascii_contains_case_insensitive(const char *text, const char *query)
{
    const size_t query_len = strlen(query);
    if (query_len == 0) {
        return false;
    }

    for (const char *start = text; *start; start++) {
        size_t i = 0;
        while (i < query_len && start[i] &&
               tolower((unsigned char)start[i]) == tolower((unsigned char)query[i])) {
            i++;
        }
        if (i == query_len) {
            return true;
        }
    }
    return false;
}

bool city_database_init(void)
{
    return true;
}

size_t city_database_count(void)
{
    return DATABASE_COUNT;
}

bool city_database_get(uint32_t index, city_db_record_t *record)
{
    if (!record || index >= DATABASE_COUNT) {
        return false;
    }
    *record = database[index];
    return true;
}

uint32_t city_database_search(const char *query, uint32_t limit,
                              city_db_record_t *matches, uint32_t *match_indexes)
{
    if (!query || !*query || !matches || !match_indexes || limit == 0) {
        return 0;
    }

    uint32_t found = 0;
    for (uint32_t i = 0; i < DATABASE_COUNT && found < limit; i++) {
        if (ascii_contains_case_insensitive(database[i].name, query) ||
            ascii_contains_case_insensitive(database[i].country, query)) {
            matches[found] = database[i];
            match_indexes[found] = i;
            found++;
        }
    }
    return found;
}
