#include "disguise.h"
#include "app_config.h"

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#include "nvs.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "cJSON.h"

static const char *TAG = "disguise";
static const char *NVS_KEY = "disguise";

static disguise_t s_current;

disguise_t *disguise_current(void) { return &s_current; }

void disguise_init_defaults(void)
{
    static const uint8_t def_bssid[6] = ALGHUL_DEFAULT_AP_BSSID;
    memset(&s_current, 0, sizeof(s_current));
    memcpy(s_current.ap_bssid, def_bssid, 6);
    s_current.beacon_interval = ALGHUL_DEFAULT_BEACON_TU;
    s_current.tx_power        = ALGHUL_DEFAULT_TX_POWER;
    s_current.vendor_ie_enabled = false;
}

esp_err_t disguise_load(void)
{
    disguise_init_defaults();

    nvs_handle_t h;
    esp_err_t err = nvs_open(ALGHUL_NVS_NAMESPACE, NVS_READONLY, &h);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "no saved disguise (%s), using defaults", esp_err_to_name(err));
        return ESP_OK;
    }
    size_t len = sizeof(disguise_t);
    disguise_t tmp;
    err = nvs_get_blob(h, NVS_KEY, &tmp, &len);
    nvs_close(h);
    if (err == ESP_OK && len == sizeof(disguise_t)) {
        s_current = tmp;
        ESP_LOGI(TAG, "loaded disguise from NVS");
    } else {
        ESP_LOGW(TAG, "disguise blob absent/mismatched, using defaults");
    }
    return ESP_OK;
}

esp_err_t disguise_save(void)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(ALGHUL_NVS_NAMESPACE, NVS_READWRITE, &h);
    if (err != ESP_OK) return err;
    err = nvs_set_blob(h, NVS_KEY, &s_current, sizeof(s_current));
    if (err == ESP_OK) err = nvs_commit(h);
    nvs_close(h);
    return err;
}

esp_err_t disguise_parse_mac(const char *str, uint8_t out[6])
{
    if (!str) return ESP_ERR_INVALID_ARG;
    int v[6];
    int n = sscanf(str, "%x:%x:%x:%x:%x:%x",
                   &v[0], &v[1], &v[2], &v[3], &v[4], &v[5]);
    if (n != 6) return ESP_ERR_INVALID_ARG;
    for (int i = 0; i < 6; i++) {
        if (v[i] < 0 || v[i] > 0xFF) return ESP_ERR_INVALID_ARG;
        out[i] = (uint8_t)v[i];
    }
    return ESP_OK;
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// Parse an even-length hex string into bytes. Returns count, or -1 on error.
static int parse_hex(const char *s, uint8_t *out, int max)
{
    int len = strlen(s);
    if (len % 2 != 0 || len / 2 > max) return -1;
    for (int i = 0; i < len / 2; i++) {
        int hi = hexval(s[2 * i]), lo = hexval(s[2 * i + 1]);
        if (hi < 0 || lo < 0) return -1;
        out[i] = (uint8_t)((hi << 4) | lo);
    }
    return len / 2;
}

esp_err_t disguise_merge_json(const char *json)
{
    cJSON *root = cJSON_Parse(json);
    if (!root) return ESP_ERR_INVALID_ARG;

    cJSON *j;
    if ((j = cJSON_GetObjectItem(root, "bssid")) && cJSON_IsString(j)) {
        uint8_t mac[6];
        if (disguise_parse_mac(j->valuestring, mac) == ESP_OK) {
            memcpy(s_current.ap_bssid, mac, 6);
        }
    }
    if ((j = cJSON_GetObjectItem(root, "beacon_interval")) && cJSON_IsNumber(j)) {
        int bi = j->valueint;
        if (bi >= 100 && bi <= 60000) s_current.beacon_interval = (uint16_t)bi;
    }
    if ((j = cJSON_GetObjectItem(root, "tx_power")) && cJSON_IsNumber(j)) {
        int tp = j->valueint;
        if (tp >= 8 && tp <= 84) s_current.tx_power = (int8_t)tp;
    }
    if ((j = cJSON_GetObjectItem(root, "vendor_ie"))) {
        if (cJSON_IsBool(j) && !cJSON_IsTrue(j)) {
            s_current.vendor_ie_enabled = false;
        } else if (cJSON_IsObject(j)) {
            cJSON *oui = cJSON_GetObjectItem(j, "oui");
            cJSON *pl  = cJSON_GetObjectItem(j, "payload_hex");
            if (oui && cJSON_IsString(oui)) {
                int o[3];
                if (sscanf(oui->valuestring, "%x:%x:%x", &o[0], &o[1], &o[2]) == 3) {
                    s_current.vendor_oui[0] = (uint8_t)o[0];
                    s_current.vendor_oui[1] = (uint8_t)o[1];
                    s_current.vendor_oui[2] = (uint8_t)o[2];
                }
            }
            if (pl && cJSON_IsString(pl)) {
                int n = parse_hex(pl->valuestring, s_current.vendor_payload,
                                  DISGUISE_VENDOR_PAYLOAD_MAX);
                if (n >= 0) s_current.vendor_payload_len = (uint8_t)n;
            }
            s_current.vendor_ie_enabled = true;
        }
    }

    cJSON_Delete(root);
    return ESP_OK;
}

char *disguise_to_json(void)
{
    cJSON *root = cJSON_CreateObject();
    char mac[18];
    snprintf(mac, sizeof(mac), "%02x:%02x:%02x:%02x:%02x:%02x",
             s_current.ap_bssid[0], s_current.ap_bssid[1], s_current.ap_bssid[2],
             s_current.ap_bssid[3], s_current.ap_bssid[4], s_current.ap_bssid[5]);
    cJSON_AddStringToObject(root, "bssid", mac);
    cJSON_AddNumberToObject(root, "beacon_interval", s_current.beacon_interval);
    cJSON_AddNumberToObject(root, "tx_power", s_current.tx_power);
    if (s_current.vendor_ie_enabled) {
        cJSON *v = cJSON_CreateObject();
        char oui[9];
        snprintf(oui, sizeof(oui), "%02x:%02x:%02x",
                 s_current.vendor_oui[0], s_current.vendor_oui[1], s_current.vendor_oui[2]);
        cJSON_AddStringToObject(v, "oui", oui);
        char payhex[2 * DISGUISE_VENDOR_PAYLOAD_MAX + 1];
        for (int i = 0; i < s_current.vendor_payload_len; i++)
            snprintf(payhex + 2 * i, 3, "%02x", s_current.vendor_payload[i]);
        payhex[2 * s_current.vendor_payload_len] = '\0';
        cJSON_AddStringToObject(v, "payload_hex", payhex);
        cJSON_AddItemToObject(root, "vendor_ie", v);
    } else {
        cJSON_AddBoolToObject(root, "vendor_ie", false);
    }
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return out;  // caller frees
}
