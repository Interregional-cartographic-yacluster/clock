idf_component_register(
    SRCS
        "clock.c"
        "city_database.c"
        "My_montserrat_16.c"
    INCLUDE_DIRS
        "."
    REQUIRES
        driver
        esp_event
        esp_http_server
        esp_lcd
        esp_netif
        esp_partition
        esp_timer
        esp_wifi
        lvgl
        nvs_flash
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE LV_LVGL_H_INCLUDE_SIMPLE)
