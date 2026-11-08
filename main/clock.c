#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "driver/spi_master.h"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lvgl.h"
#include "nvs_flash.h"

// Display orientation and panel-specific offsets.
#define SWAP_XY             true
#define MIRROR_X            false
#define MIRROR_Y            true
#define INVERT_COLOR        false
#define COLOR_ORDER         LCD_RGB_ELEMENT_ORDER_RGB
#define GAP_X               18
#define GAP_Y               82

// ESP32-WROOM-32D -> ST7789 connections.
#define LCD_HOST            SPI2_HOST
#define LCD_PIN_SCLK        18
#define LCD_PIN_MOSI        23
#define LCD_PIN_CS          5
#define LCD_PIN_DC          15
#define LCD_PIN_RST         4
#define LCD_WIDTH           284
#define LCD_HEIGHT          76
#define LCD_BITS_PER_PIXEL  16

#define UI_PERIOD_MS        20
#define CLOCK_POLL_MS       200
#define UI_TASK_STACK_SIZE  6144
#define UI_TASK_PRIORITY    4
#define TIME_VALID_EPOCH    1577836800  // 2020-01-01 00:00:00 UTC

static const char *TAG = "clock";
static const char *WIFI_TAG = "wifi";

static lv_obj_t *label_time;
static lv_obj_t *label_date;
static esp_timer_handle_t wifi_reconnect_timer;
static uint32_t wifi_retry_count;

LV_FONT_DECLARE(My_montserrat_16);

static void set_label_text(lv_obj_t *label, const char *text)
{
    // Avoid invalidating and redrawing a label when its value has not changed.
    if (strcmp(lv_label_get_text(label), text) != 0) {
        lv_label_set_text(label, text);
    }
}

static void update_clock(void)
{
    static time_t previous_now = (time_t)-1;
    const time_t now = time(NULL);

    if (now == previous_now) {
        return;
    }
    previous_now = now;

    if (now < TIME_VALID_EPOCH) {
        set_label_text(label_time, "--:--:--");
        set_label_text(label_date, "--.--.----");
        return;
    }

    struct tm timeinfo;
    char time_buf[9];
    char date_buf[11];

    localtime_r(&now, &timeinfo);
    strftime(time_buf, sizeof(time_buf), "%H:%M:%S", &timeinfo);
    strftime(date_buf, sizeof(date_buf), "%d.%m.%Y", &timeinfo);
    set_label_text(label_time, time_buf);
    set_label_text(label_date, date_buf);
}

static void clock_timer_cb(lv_timer_t *timer)
{
    (void)timer;
    update_clock();
}

static void schedule_wifi_reconnect(void)
{
    if (esp_timer_is_active(wifi_reconnect_timer)) {
        return;
    }

    // Delays: 1, 2, 4, 8, 16, then 30 seconds. Never reconnect in a tight loop.
    uint32_t delay_sec = 1U << (wifi_retry_count < 5 ? wifi_retry_count : 5);
    if (delay_sec > 30) {
        delay_sec = 30;
    }
    if (wifi_retry_count < UINT32_MAX) {
        wifi_retry_count++;
    }

    ESP_LOGI(WIFI_TAG, "Reconnecting in %lu seconds", (unsigned long)delay_sec);
    esp_err_t err = esp_timer_start_once(wifi_reconnect_timer,
                                         (uint64_t)delay_sec * 1000000ULL);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(WIFI_TAG, "Failed to schedule reconnect: %s", esp_err_to_name(err));
    }
}

static void wifi_reconnect_cb(void *arg)
{
    (void)arg;
    esp_err_t err = esp_wifi_connect();
    if (err != ESP_OK) {
        ESP_LOGW(WIFI_TAG, "Connection request failed: %s", esp_err_to_name(err));
        schedule_wifi_reconnect();
    }
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    (void)arg;

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        wifi_retry_count = 0;
        esp_err_t err = esp_wifi_connect();
        if (err != ESP_OK) {
            ESP_LOGE(WIFI_TAG, "Initial connection failed: %s", esp_err_to_name(err));
            schedule_wifi_reconnect();
        }
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        const wifi_event_sta_disconnected_t *event = event_data;
        ESP_LOGW(WIFI_TAG, "Disconnected (reason %d)", event ? event->reason : -1);
        schedule_wifi_reconnect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        const ip_event_got_ip_t *event = event_data;
        wifi_retry_count = 0;
        if (esp_timer_is_active(wifi_reconnect_timer)) {
            esp_timer_stop(wifi_reconnect_timer);
        }
        ESP_LOGI(WIFI_TAG, "IP address: " IPSTR, IP2STR(&event->ip_info.ip));
    }
}

static void wifi_init(void)
{
    const bool wifi_configured = CONFIG_CLOCK_WIFI_SSID[0] != '\0';
    if (!wifi_configured) {
        ESP_LOGW(WIFI_TAG, "Wi-Fi SSID is empty; configure it with idf.py menuconfig");
    }

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    if (!wifi_configured) {
        return;
    }
    ESP_ERROR_CHECK(esp_netif_create_default_wifi_sta() ? ESP_OK : ESP_FAIL);

    wifi_init_config_t init_config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_config));

    const esp_timer_create_args_t timer_args = {
        .callback = wifi_reconnect_cb,
        .name = "wifi_reconnect",
    };
    ESP_ERROR_CHECK(esp_timer_create(&timer_args, &wifi_reconnect_timer));

    esp_event_handler_instance_t wifi_events;
    esp_event_handler_instance_t ip_events;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, NULL, &wifi_events));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event_handler, NULL, &ip_events));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = CONFIG_CLOCK_WIFI_SSID,
            .password = CONFIG_CLOCK_WIFI_PASSWORD,
            .threshold.authmode = CONFIG_CLOCK_WIFI_PASSWORD[0] == '\0'
                                  ? WIFI_AUTH_OPEN : WIFI_AUTH_WPA2_PSK,
            .pmf_cfg = {
                .capable = true,
                .required = false,
            },
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGI(WIFI_TAG, "Connecting to %s", CONFIG_CLOCK_WIFI_SSID);
}

static void time_sync_cb(struct timeval *tv)
{
    (void)tv;
    time_t now = time(NULL);
    struct tm timeinfo;
    char buf[32];

    localtime_r(&now, &timeinfo);
    strftime(buf, sizeof(buf), "%d.%m.%Y %H:%M:%S %Z", &timeinfo);
    ESP_LOGI(TAG, "Time synchronized: %s", buf);
}

static void time_init(void)
{
    setenv("TZ", CONFIG_CLOCK_TIMEZONE, 1);
    tzset();

    esp_sntp_config_t config = ESP_NETIF_SNTP_DEFAULT_CONFIG(CONFIG_CLOCK_NTP_SERVER);
    config.wait_for_sync = false;  // No semaphore is needed for asynchronous updates.
    config.sync_cb = time_sync_cb;
    ESP_ERROR_CHECK(esp_netif_sntp_init(&config));
    ESP_LOGI(TAG, "SNTP started (server: %s)", CONFIG_CLOCK_NTP_SERVER);
}

static void flush_cb(lv_display_t *display, const lv_area_t *area, uint8_t *color_map)
{
    esp_lcd_panel_handle_t panel = lv_display_get_user_data(display);
    uint16_t *pixels = (uint16_t *)color_map;
    const int32_t pixel_count = lv_area_get_width(area) * lv_area_get_height(area);

    // ST7789 expects big-endian RGB565, while ESP32 is little-endian.
    for (int32_t i = 0; i < pixel_count; i++) {
        pixels[i] = __builtin_bswap16(pixels[i]);
    }

    esp_err_t err = esp_lcd_panel_draw_bitmap(panel, area->x1, area->y1,
                                              area->x2 + 1, area->y2 + 1, pixels);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Display update failed: %s", esp_err_to_name(err));
    }
    lv_display_flush_ready(display);
}

static void lvgl_task(void *arg)
{
    (void)arg;

    for (;;) {
        uint32_t delay_ms = lv_timer_handler();
        if (delay_ms < 1) {
            delay_ms = 1;
        } else if (delay_ms > UI_PERIOD_MS) {
            delay_ms = UI_PERIOD_MS;
        }

        TickType_t delay_ticks = pdMS_TO_TICKS(delay_ms);
        vTaskDelay(delay_ticks > 0 ? delay_ticks : 1);
    }
}

static bool display_init(void)
{
    const size_t buffer_size = LCD_WIDTH * CONFIG_CLOCK_LCD_BUFFER_LINES * sizeof(uint16_t);

    spi_bus_config_t bus_config = {
        .sclk_io_num = LCD_PIN_SCLK,
        .mosi_io_num = LCD_PIN_MOSI,
        .miso_io_num = -1,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = buffer_size,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &bus_config, SPI_DMA_CH_AUTO));

    esp_lcd_panel_io_handle_t io_handle;
    esp_lcd_panel_io_spi_config_t io_config = {
        .cs_gpio_num = LCD_PIN_CS,
        .dc_gpio_num = LCD_PIN_DC,
        .spi_mode = 0,
        .pclk_hz = CONFIG_CLOCK_LCD_SPI_CLOCK_HZ,
        .trans_queue_depth = 10,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(LCD_HOST, &io_config, &io_handle));

    esp_lcd_panel_handle_t panel;
    esp_lcd_panel_dev_config_t panel_config = {
        .reset_gpio_num = LCD_PIN_RST,
        .bits_per_pixel = LCD_BITS_PER_PIXEL,
        .rgb_ele_order = COLOR_ORDER,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io_handle, &panel_config, &panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_set_gap(panel, GAP_X, GAP_Y));
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel, INVERT_COLOR));
    ESP_ERROR_CHECK(esp_lcd_panel_mirror(panel, MIRROR_X, MIRROR_Y));
    ESP_ERROR_CHECK(esp_lcd_panel_swap_xy(panel, SWAP_XY));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel, true));

    lv_init();
    lv_display_t *display = lv_display_create(LCD_WIDTH, LCD_HEIGHT);
    if (!display) {
        ESP_LOGE(TAG, "Failed to create LVGL display");
        return false;
    }

    uint8_t *buffer1 = heap_caps_malloc(buffer_size, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    uint8_t *buffer2 = heap_caps_malloc(buffer_size, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    if (!buffer1 || !buffer2) {
        ESP_LOGE(TAG, "Not enough DMA memory for two %u-byte buffers", (unsigned)buffer_size);
        heap_caps_free(buffer1);
        heap_caps_free(buffer2);
        lv_display_delete(display);
        return false;
    }

    lv_display_set_color_format(display, LV_COLOR_FORMAT_RGB565);
    lv_display_set_flush_cb(display, flush_cb);
    lv_display_set_user_data(display, panel);
    lv_display_set_buffers(display, buffer1, buffer2, buffer_size,
                           LV_DISPLAY_RENDER_MODE_PARTIAL);
    return true;
}

static lv_obj_t *create_text_label(lv_obj_t *parent, const char *text)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, &My_montserrat_16, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0x00FFCC), 0);
    lv_obj_set_style_text_opa(label, LV_OPA_COVER, 0);
    lv_label_set_text(label, text);
    return label;
}

static void ui_init(void)
{
    lv_obj_t *screen = lv_display_get_screen_active(lv_display_get_default());
    lv_obj_remove_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, 0);

    lv_obj_t *container = lv_obj_create(screen);
    lv_obj_set_size(container, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(container, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(container, LV_FLEX_ALIGN_CENTER,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(container, 6, 0);
    lv_obj_set_style_pad_all(container, 0, 0);
    lv_obj_set_style_bg_opa(container, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(container, 0, 0);
    lv_obj_remove_flag(container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_align(container, LV_ALIGN_CENTER, 0, 0);

    label_date = create_text_label(container, "--.--.----");
    label_time = create_text_label(container, "--:--:--");
    create_text_label(container, "КосмоКРЯК");

    // This timer and all other LVGL operations run only in lvgl_task.
    lv_timer_create(clock_timer_cb, CLOCK_POLL_MS, NULL);
}

void app_main(void)
{
    ESP_LOGI(TAG, "Starting horizontal clock");

    wifi_init();
    time_init();

    if (!display_init()) {
        ESP_LOGE(TAG, "Display initialization aborted");
        return;
    }
    ui_init();

    BaseType_t task_created = xTaskCreate(lvgl_task, "lvgl", UI_TASK_STACK_SIZE,
                                          NULL, UI_TASK_PRIORITY, NULL);
    if (task_created != pdPASS) {
        ESP_LOGE(TAG, "Failed to create LVGL task");
        return;
    }
}
