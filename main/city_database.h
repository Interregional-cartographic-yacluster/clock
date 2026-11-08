#ifndef CITY_DATABASE_H
#define CITY_DATABASE_H

#include <stdbool.h>
#include <stdint.h>

#define CITY_DB_NAME_MAX 96
#define CITY_DB_COUNTRY_MAX 96
#define CITY_DB_TZ_MAX 64

typedef struct {
    char name[CITY_DB_NAME_MAX];
    char country[CITY_DB_COUNTRY_MAX];
    char timezone[CITY_DB_TZ_MAX];
} city_db_record_t;

bool city_database_init(void);
uint32_t city_database_count(void);
bool city_database_get(uint32_t index, city_db_record_t *record);
uint32_t city_database_search(const char *query,
                              uint32_t limit,
                              city_db_record_t *records,
                              uint32_t *indexes);

#endif
