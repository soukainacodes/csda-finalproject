// The Watcher's eyes: a classic ESP32 in promiscuous mode that captures beacons
// and probe responses and streams one JSON record per frame to the laptop over
// USB serial. Passive and receive-only: it never transmits, never deauths,
// never jams. It exists because the laptop's Realtek adapter cannot do monitor
// mode. See docs/ETHICS.md.
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_timer.h"
#include "nvs_flash.h"

#include "beacon_parse.h"

static const char *TAG = "sniffer";

// 0 = hop across channels 1..13; or set to a fixed channel (your router's) to
// avoid missing frames during a measured run. Overridable at build time.
#ifndef SNIFFER_LOCK_CHANNEL
#define SNIFFER_LOCK_CHANNEL 0
#endif

#define CAP_MAX_LEN 300
#define CAP_QUEUE   48

typedef struct {
    int8_t   rssi;
    uint8_t  ch;
    int64_t  ts;
    uint16_t len;
    uint8_t  buf[CAP_MAX_LEN];
} cap_t;

static QueueHandle_t s_q;

// Runs in the WiFi task context: keep it short, just copy and enqueue.
static void promisc_cb(void *buf, wifi_promiscuous_pkt_type_t type)
{
    if (type != WIFI_PKT_MGMT) return;
    const wifi_promiscuous_pkt_t *p = (const wifi_promiscuous_pkt_t *)buf;

    uint8_t subtype = (p->payload[0] & 0xF0) >> 4;
    if (subtype != 8 && subtype != 5) return;  // beacon / probe response only

    cap_t c;
    c.rssi = p->rx_ctrl.rssi;
    c.ch   = p->rx_ctrl.channel;
    c.ts   = esp_timer_get_time();
    int l  = p->rx_ctrl.sig_len;
    if (l > CAP_MAX_LEN) l = CAP_MAX_LEN;
    if (l < 0) return;
    c.len = (uint16_t)l;
    memcpy(c.buf, p->payload, l);
    xQueueSend(s_q, &c, 0);  // drop if full rather than block the driver
}

static void parser_task(void *arg)
{
    cap_t c;
    while (1) {
        if (xQueueReceive(s_q, &c, portMAX_DELAY) == pdTRUE) {
            beacon_parse_and_print(c.buf, c.len, c.rssi, c.ch, c.ts);
        }
    }
}

static void channel_task(void *arg)
{
#if SNIFFER_LOCK_CHANNEL
    esp_wifi_set_channel(SNIFFER_LOCK_CHANNEL, WIFI_SECOND_CHAN_NONE);
    ESP_LOGI(TAG, "channel locked to %d", SNIFFER_LOCK_CHANNEL);
    vTaskDelete(NULL);
#else
    int ch = 1;
    ESP_LOGI(TAG, "hopping channels 1..13");
    while (1) {
        esp_wifi_set_channel(ch, WIFI_SECOND_CHAN_NONE);
        ch = (ch % 13) + 1;
        vTaskDelay(pdMS_TO_TICKS(300));
    }
#endif
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));  // needed to RX; we never connect
    ESP_ERROR_CHECK(esp_wifi_start());
    // Critical for a sniffer: disable modem power-save, otherwise the radio sleeps
    // between beacons (STA default) and promiscuous capture misses most frames.
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    s_q = xQueueCreate(CAP_QUEUE, sizeof(cap_t));
    xTaskCreate(parser_task, "parser", 4096, NULL, 5, NULL);

    wifi_promiscuous_filter_t filt = { .filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT };
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_filter(&filt));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_rx_cb(&promisc_cb));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));

    xTaskCreate(channel_task, "channel", 2048, NULL, 4, NULL);

    // Banner line the laptop capture script watches for.
    printf("{\"k\":\"sniffer_ready\",\"lock_channel\":%d}\n", SNIFFER_LOCK_CHANNEL);
    ESP_LOGI(TAG, "promiscuous capture running");
}
