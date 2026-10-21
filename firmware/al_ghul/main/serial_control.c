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
