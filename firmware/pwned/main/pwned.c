// AL-GHUL "owned" payload.
//
// This is the firmware the Watcher pushes over OTA the instant it takes the twin
// over. It is deliberately, visibly NOT the twin any more:
//   - its SoftAP announces  NEUTRALIZED_BY_THE_WATCHER  (seen on every phone)
//   - the onboard RGB LED glows red
//   - it taunts over the serial console
// It does not clone, relay, or capture anything. Its whole job is to make
// "we control the attacker's hardware now" undeniable on a projector.
//
// The lesson it proves: with flash encryption and secure boot OFF (the ESP32
// default), whoever holds the OTA channel can replace the firmware wholesale.
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "led_strip.h"

#define OWNED_SSID "NEUTRALIZED_BY_THE_WATCHER"
#define LED_GPIO   48            // ESP32-S3-DevKitC-1 onboard WS2812 (adjust per board)

static const char *TAG = "pwned";

static void wifi_owned_ap(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t ap = { 0 };
    strncpy((char *)ap.ap.ssid, OWNED_SSID, sizeof(ap.ap.ssid));
    ap.ap.ssid_len = strlen(OWNED_SSID);
    ap.ap.channel = 6;
    ap.ap.max_connection = 4;
    ap.ap.authmode = WIFI_AUTH_OPEN;     // open on purpose: the point is the name

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGW(TAG, "SoftAP up: \"%s\"", OWNED_SSID);
}

static led_strip_handle_t s_strip;

static void led_task(void *arg)
{
    led_strip_config_t sc = { .strip_gpio_num = LED_GPIO, .max_leds = 1 };
    led_strip_rmt_config_t rc = { .resolution_hz = 10 * 1000 * 1000 };
    if (led_strip_new_rmt_device(&sc, &rc, &s_strip) != ESP_OK || !s_strip) {
        ESP_LOGW(TAG, "no addressable LED here; the SSID is proof enough");
        vTaskDelete(NULL);
        return;
    }
    // slow red breathing, forever
    while (1) {
        for (int v = 10; v <= 120; v += 6) {
            led_strip_set_pixel(s_strip, 0, v, 0, 0);
            led_strip_refresh(s_strip);
            vTaskDelay(pdMS_TO_TICKS(25));
        }
        for (int v = 120; v >= 10; v -= 6) {
            led_strip_set_pixel(s_strip, 0, v, 0, 0);
            led_strip_refresh(s_strip);
            vTaskDelay(pdMS_TO_TICKS(25));
        }
    }
}

static void taunt_task(void *arg)
{
    while (1) {
        ESP_LOGW(TAG, "This board belongs to the Watcher now. Flash encryption was off.");
        vTaskDelay(pdMS_TO_TICKS(3000));
    }
}

void app_main(void)
{
    esp_err_t e = nvs_flash_init();
    if (e == ESP_ERR_NVS_NO_FREE_PAGES || e == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }
    ESP_LOGW(TAG, "=== AL-GHUL has been NEUTRALIZED and REFLASHED by the Watcher ===");
    wifi_owned_ap();
    xTaskCreate(led_task, "led", 3072, NULL, 4, NULL);
    xTaskCreate(taunt_task, "taunt", 3072, NULL, 3, NULL);
}
