#include <stdio.h>
#include <string.h>
#include <time.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_panel_ops.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "lvgl.h"

// ================================================
//  НАСТРОЙКИ ОТОБРАЖЕНИЯ
// ================================================
#define SWAP_XY        true
#define MIRROR_X       false
#define MIRROR_Y       true
#define INVERT_COLOR   false
#define COLOR_ORDER    LCD_RGB_ELEMENT_ORDER_RGB
#define GAP_X          18
#define GAP_Y          82

// ================================================
//  НАСТРОЙКИ ДИСПЛЕЯ (СООТВЕТСТВИЕ ПИНОВ)
// ================================================
#define LCD_HOST       SPI2_HOST
#define LCD_PIN_SCLK   18   // SCL (SPI Clock)  -> GPIO18
#define LCD_PIN_MOSI   23   // SDA (SPI MOSI)   -> GPIO23
#define LCD_PIN_CS     5    // CS               -> GPIO5
#define LCD_PIN_DC     15   // DC               -> GPIO15
#define LCD_PIN_RST    4    // RST              -> GPIO4
// BL (подсветка) подключена к GND, пина нет

#define LCD_WIDTH      284
#define LCD_HEIGHT     76

// ================================================
//  НАСТРОЙКИ WIFI
// ================================================
#define WIFI_SSID      "WIFI_SSID"
#define WIFI_PASS      "WIFI_PASS"

// ================================================
//  НАСТРОЙКИ ВРЕМЕНИ
// ================================================
#define NTP_SERVER     "pool.ntp.org"

static const char *TAG = "CLOCK";
static lv_obj_t *label_time = NULL;
static lv_obj_t *label_date = NULL;
static lv_obj_t *label_text = NULL;

LV_FONT_DECLARE(My_montserrat_16);

static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                                int32_t event_id, void* event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        esp_wifi_connect();
        ESP_LOGI(TAG, "Retry to connect to Wi-Fi");
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Got IP:" IPSTR, IP2STR(&event->ip_info.ip));
    }
}

static void wifi_init(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    esp_event_handler_instance_t instance_any_id, instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &instance_got_ip));
    wifi_config_t wifi_config = { .sta = { .ssid = WIFI_SSID, .password = WIFI_PASS } };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGI(TAG, "Wi-Fi initialized, connecting...");
}

static void sntp_init(void) {
    ESP_LOGI(TAG, "Initializing SNTP");
    esp_sntp_config_t config = ESP_NETIF_SNTP_DEFAULT_CONFIG(NTP_SERVER);
    esp_netif_sntp_init(&config);
    setenv("TZ", "MSK-3", 1);
    tzset();
    time_t now = 0;
    struct tm timeinfo = { 0 };
    int retry = 0;
    while (timeinfo.tm_year < (2016 - 1900) && ++retry < 20) {
        ESP_LOGI(TAG, "Waiting for NTP time... (%d/20)", retry);
        vTaskDelay(pdMS_TO_TICKS(1000));
        time(&now);
        localtime_r(&now, &timeinfo);
    }
    if (retry == 20) ESP_LOGE(TAG, "Failed to get NTP time");
    else ESP_LOGI(TAG, "Time synchronized: %s", asctime(&timeinfo));
}

static void update_display(void) {
    time_t now;
    struct tm timeinfo;
    time(&now);
    localtime_r(&now, &timeinfo);

    char time_buf[16];
    char date_buf[16];
    strftime(time_buf, sizeof(time_buf), "%H:%M:%S", &timeinfo);
    strftime(date_buf, sizeof(date_buf), "%d.%m.%Y", &timeinfo);

    if (label_date) lv_label_set_text(label_date, date_buf);
    if (label_time) lv_label_set_text(label_time, time_buf);

    lv_display_t *disp = lv_display_get_default();
    if (disp) lv_refr_now(disp);
}

static void clock_update_task(void *arg) {
    TickType_t last_wake = xTaskGetTickCount();
    while (1) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(1000));
        update_display();
    }
}

static void flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *color_map) {
    esp_lcd_panel_handle_t panel = (esp_lcd_panel_handle_t)lv_display_get_user_data(disp);
    
    int32_t w = lv_area_get_width(area);
    int32_t h = lv_area_get_height(area);
    uint16_t *buf = (uint16_t*)color_map;
    int32_t px_cnt = w * h;
    for (int32_t i = 0; i < px_cnt; i++) {
        buf[i] = (buf[i] >> 8) | (buf[i] << 8);
    }
    
    esp_lcd_panel_draw_bitmap(panel, area->x1, area->y1, area->x2 + 1, area->y2 + 1, buf);
    lv_display_flush_ready(disp);
}

static void lvgl_task(void *arg) {
    while (1) {
        uint32_t delay = lv_timer_handler();
        vTaskDelay(pdMS_TO_TICKS(delay > 0 ? delay : 1));
    }
}

static void lvgl_display_init(void) {
    spi_bus_config_t buscfg = {
        .sclk_io_num = LCD_PIN_SCLK,
        .mosi_io_num = LCD_PIN_MOSI,
        .miso_io_num = -1,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = ((LCD_WIDTH * LCD_HEIGHT * sizeof(uint16_t) + 3) & ~3),
    };
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &buscfg, SPI_DMA_CH_AUTO));

    esp_lcd_panel_io_handle_t io_handle = NULL;
    esp_lcd_panel_io_spi_config_t io_config = {
        .cs_gpio_num = LCD_PIN_CS,
        .dc_gpio_num = LCD_PIN_DC,
        .spi_mode = 0,
        .pclk_hz = 10 * 1000 * 1000,
        .trans_queue_depth = 10,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(LCD_HOST, &io_config, &io_handle));

    esp_lcd_panel_handle_t panel_handle = NULL;
    esp_lcd_panel_dev_config_t panel_config = {
        .reset_gpio_num = LCD_PIN_RST,
        .bits_per_pixel = 16,
        .rgb_ele_order = COLOR_ORDER,
        .vendor_config = NULL,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io_handle, &panel_config, &panel_handle));

    esp_lcd_panel_reset(panel_handle);
    esp_lcd_panel_init(panel_handle);
    esp_lcd_panel_set_gap(panel_handle, GAP_X, GAP_Y);
    esp_lcd_panel_invert_color(panel_handle, INVERT_COLOR);
    esp_lcd_panel_mirror(panel_handle, MIRROR_X, MIRROR_Y);
    esp_lcd_panel_swap_xy(panel_handle, SWAP_XY);
    esp_lcd_panel_disp_on_off(panel_handle, true);

    // BL (подсветка) подключена к GND — управление не требуется

    lv_init();

    lv_display_t *disp = lv_display_create(LCD_WIDTH, LCD_HEIGHT);
    lv_display_set_color_format(disp, LV_COLOR_FORMAT_RGB565);
    lv_display_set_flush_cb(disp, flush_cb);
    lv_display_set_user_data(disp, panel_handle);

    size_t buf_size = LCD_WIDTH * 40 * sizeof(uint16_t);
    if (buf_size % 4 != 0) buf_size += 4 - (buf_size % 4);
    
    uint8_t *buf1 = heap_caps_malloc(buf_size, MALLOC_CAP_DMA);
    uint8_t *buf2 = heap_caps_malloc(buf_size, MALLOC_CAP_DMA);
    if (!buf1 || !buf2) {
        ESP_LOGE(TAG, "Failed to allocate LVGL buffers");
        return;
    }
    lv_display_set_buffers(disp, buf1, buf2, buf_size, LV_DISPLAY_RENDER_MODE_PARTIAL);
}

void app_main(void) {
    ESP_LOGI(TAG, "Starting horizontal clock");

    wifi_init();
    sntp_init();

    lvgl_display_init();

    lv_obj_t *scr = lv_display_get_screen_active(lv_display_get_default());
    lv_obj_clean(scr);

    lv_obj_set_style_bg_color(scr, lv_color_hex(0x000000), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);

    lv_obj_t *cont = lv_obj_create(scr);
    lv_obj_set_size(cont, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(cont, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(cont, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(cont, 6, 0);
    lv_obj_set_style_pad_all(cont, 0, 0);
    lv_obj_set_style_bg_opa(cont, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(cont, 0, 0);
    lv_obj_align(cont, LV_ALIGN_CENTER, 0, 0);

    label_date = lv_label_create(cont);
    lv_obj_set_style_text_font(label_date, &My_montserrat_16, 0);
    lv_obj_set_style_text_color(label_date, lv_color_hex(0x00FFCC), 0);
    lv_obj_set_style_text_opa(label_date, LV_OPA_COVER, 0);

    label_time = lv_label_create(cont);
    lv_obj_set_style_text_font(label_time, &My_montserrat_16, 0);
    lv_obj_set_style_text_color(label_time, lv_color_hex(0x00FFCC), 0);
    lv_obj_set_style_text_opa(label_time, LV_OPA_COVER, 0);

    label_text = lv_label_create(cont);
    lv_obj_set_style_text_font(label_text, &My_montserrat_16, 0);
    lv_obj_set_style_text_color(label_text, lv_color_hex(0x00FFCC), 0);
    lv_obj_set_style_text_opa(label_text, LV_OPA_COVER, 0);
    lv_label_set_text(label_text, "КосмоКРЯК");

    update_display();

    xTaskCreate(clock_update_task, "clock_update", 8192, NULL, 1, NULL);
    xTaskCreate(lvgl_task, "lvgl", 8192, NULL, 2, NULL);

    vTaskDelete(NULL);
}