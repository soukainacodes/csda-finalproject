// AL-GHUL main orchestrator.
//
// PROJECT: "AL-GHUL vs the Watcher" (CSDA final project, RU, Jacky Mallett).
// AL-GHUL is the ATTACKER half: a controllable evil-twin access point used only
// to GENERATE a measurable adversary so the Watcher (the ML detector on the
// laptop) can be trained and scored across the arms-race rounds. It runs ONLY on
// the student's own ESP32-S3, cloning HER OWN router on HER OWN isolated lab,
// with HER OWN phone as the only client. No deauthentication, no jamming: it
// only out-signals (louder beacon) and relays. See docs/ETHICS.md.
//
// Boot sequence: NVS -> netif/event loop -> load disguise -> WiFi AP+STA ->
// on uplink IP, enable the NAT relay -> start the HTTP control/OTA server.
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#include "app_config.h"
#include "disguise.h"
#include "wifi_twin.h"
#include "napt_relay.h"
#include "control_server.h"
#include "serial_control.h"

static const char *TAG = "al_ghul";

static void on_wifi(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    switch (id) {
    case WIFI_EVENT_STA_START:
        esp_wifi_connect();
        break;
    case WIFI_EVENT_STA_DISCONNECTED:
        ESP_LOGW(TAG, "uplink dropped, reconnecting");
        esp_wifi_connect();
        break;
    case WIFI_EVENT_AP_STACONNECTED:
        ESP_LOGI(TAG, "a client joined the clone");
        break;
    case WIFI_EVENT_AP_STADISCONNECTED:
        ESP_LOGI(TAG, "a client left the clone");
        break;
    default:
        break;
    }
}

static void on_ip(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "uplink up, IP " IPSTR, IP2STR(&e->ip_info.ip));
        // Turn on the transparent relay now that we have a working uplink.
        napt_relay_enable(wifi_twin_ap_netif());
        napt_relay_set_ap_dns_from_sta(wifi_twin_ap_netif(), wifi_twin_sta_netif());
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "AL-GHUL starting (lab-only evil-twin for Watcher training)");

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    disguise_load();

    ESP_ERROR_CHECK(wifi_twin_init());
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, on_wifi, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, on_ip, NULL, NULL));

    ESP_ERROR_CHECK(wifi_twin_start(disguise_current()));
    ESP_ERROR_CHECK(control_server_start());
    serial_control_start();  // USB control: reliable even when WiFi flaps

    // Heartbeat: show uplink status AND the devices currently joined to the clone
    // (so you can watch the victim roam onto the twin, the H1 check).
    int beat = 0;
    while (1) {
        wifi_ap_record_t ap;
        bool up = (esp_wifi_sta_get_ap_info(&ap) == ESP_OK);
        wifi_sta_list_t clients;
        memset(&clients, 0, sizeof(clients));
        esp_wifi_ap_get_sta_list(&clients);
        ESP_LOGI(TAG, "alive #%d | uplink=%s | clone_clients=%d | heap=%u",
                 beat++, up ? "yes" : "no", clients.num,
                 (unsigned)esp_get_free_heap_size());
        for (int i = 0; i < clients.num; i++) {
            ESP_LOGI(TAG, "  joined %d: %02x:%02x:%02x:%02x:%02x:%02x | rssi %d",
                     i, clients.sta[i].mac[0], clients.sta[i].mac[1],
                     clients.sta[i].mac[2], clients.sta[i].mac[3],
                     clients.sta[i].mac[4], clients.sta[i].mac[5], clients.sta[i].rssi);
        }
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
