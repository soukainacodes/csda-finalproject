#include "ota_receive.h"

#include <string.h>
#include <inttypes.h>
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "ota";

#ifndef MIN
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#endif

esp_err_t ota_receive_handler(httpd_req_t *req)
{
    const esp_partition_t *target = esp_ota_get_next_update_partition(NULL);
    if (!target) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "no OTA slot");
        return ESP_FAIL;
    }
    ESP_LOGW(TAG, "OTA incoming (%d bytes) -> partition '%s' @0x%" PRIx32,
             req->content_len, target->label, target->address);

    esp_ota_handle_t handle = 0;
    esp_err_t err = esp_ota_begin(target, OTA_SIZE_UNKNOWN, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_ota_begin: %s", esp_err_to_name(err));
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "ota_begin failed");
        return ESP_FAIL;
    }

    char buf[1024];
    int remaining = req->content_len;
    while (remaining > 0) {
        int r = httpd_req_recv(req, buf, MIN(remaining, (int)sizeof(buf)));
        if (r == HTTPD_SOCK_ERR_TIMEOUT) continue;
        if (r <= 0) {
            esp_ota_abort(handle);
            ESP_LOGE(TAG, "recv failed (%d), OTA aborted", r);
            return ESP_FAIL;
        }
        err = esp_ota_write(handle, buf, r);
        if (err != ESP_OK) {
            esp_ota_abort(handle);
            ESP_LOGE(TAG, "esp_ota_write: %s", esp_err_to_name(err));
            httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "ota_write failed");
            return ESP_FAIL;
        }
        remaining -= r;
    }

    err = esp_ota_end(handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_ota_end: %s", esp_err_to_name(err));
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "image invalid");
        return ESP_FAIL;
    }
    err = esp_ota_set_boot_partition(target);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "set_boot_partition: %s", esp_err_to_name(err));
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "set_boot failed");
        return ESP_FAIL;
    }

    httpd_resp_sendstr(req, "OTA accepted; rebooting into new image\n");
    ESP_LOGW(TAG, "OTA complete, rebooting in 0.5s");
    vTaskDelay(pdMS_TO_TICKS(500));
    esp_restart();
    return ESP_OK;  // not reached
}
