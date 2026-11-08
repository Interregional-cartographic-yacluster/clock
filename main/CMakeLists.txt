idf_component_register(
    SRCS
        "clock.c"
        "city_database.c"
        "My_montserrat_16.c"
    INCLUDE_DIRS "."
    REQUIRES
        esp_lcd
        lvgl
        esp_netif
        esp_wifi
        esp_event
        nvs_flash
        esp_http_server
        esp_partition
        driver
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE LV_LVGL_H_INCLUDE_SIMPLE)
