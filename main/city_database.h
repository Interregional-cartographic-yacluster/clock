#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    const char *name;
    const char *country;
    const char *timezone;
} city_db_record_t;

bool city_database_init(void);
size_t city_database_count(void);
bool city_database_get(uint32_t index, city_db_record_t *record);
uint32_t city_database_search(const char *query, uint32_t limit,
                              city_db_record_t *matches, uint32_t *match_indexes);
