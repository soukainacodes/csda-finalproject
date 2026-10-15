// AL-GHUL KILL image, the finisher.
//
// The laptop pushes this image to AL-GHUL over its own OTA channel once the
// Watcher is confident. On boot it erases the twin's app slot, its saved
// disguise (NVS), and the OTA selector (otadata), so AL-GHUL goes dark and can
// only be revived by a physical USB re-flash. This is a remote kill-switch on
// the student's OWN board, a command it was built to obey, not an exploit, and
// it uses no deauth and no jamming.
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_partition.h"

static const char *TAG = "kill";

static void erase_part(esp_partition_type_t type, esp_partition_subtype_t sub,
                       const char *label)
{
    const esp_partition_t *p = esp_partition_find_first(type, sub, label);
    if (!p) {
        ESP_LOGW(TAG, "partition (type %d sub %d) not found, skipping", type, sub);
        return;
    }
    ESP_LOGW(TAG, "erasing '%s' @0x%" PRIx32 " size 0x%" PRIx32,
             p->label, p->address, p->size);
    esp_err_t e = esp_partition_erase_range(p, 0, p->size);
    ESP_LOGW(TAG, "  -> %s", esp_err_to_name(e));
}

void app_main(void)
{
    ESP_LOGW(TAG, "=== AL-GHUL KILL image active: wiping flash ===");

    // 1) the twin application itself
    erase_part(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_0, NULL);
    // 2) the saved disguise / config
    erase_part(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, NULL);
    // 3) the OTA boot selector, so the twin is never chosen again
    erase_part(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_OTA, NULL);

    ESP_LOGW(TAG, "=== wipe complete. AL-GHUL is dark. USB re-flash required. ===");

    // We cannot erase the slot we are executing from, so just halt here. On the
    // next power cycle the bootloader finds no valid twin and stops.
    while (1) {
        vTaskDelay(portMAX_DELAY);
    }
}
