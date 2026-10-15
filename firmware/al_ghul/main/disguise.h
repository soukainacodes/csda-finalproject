// The twin's "disguise": the small set of over-the-air parameters the attacker
// AI is allowed to vary each round to try to look more like the real router.
// These are exactly the knobs the Watcher learns to fingerprint, so this struct
// is the shared vocabulary between attacker (firmware) and defender (laptop).
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"

#define DISGUISE_VENDOR_PAYLOAD_MAX 32

typedef struct {
    uint8_t  ap_bssid[6];        // the twin's advertised BSSID (a disguise knob)
    uint16_t beacon_interval;    // TU (1 TU = 1.024 ms); timing fingerprint knob
    int8_t   tx_power;           // 0.25 dBm steps, 8..84; the "out-signal" level
    bool     vendor_ie_enabled;  // whether a vendor-specific IE is appended
    uint8_t  vendor_oui[3];      // OUI of that IE (mimic real router's vendor?)
    uint8_t  vendor_payload[DISGUISE_VENDOR_PAYLOAD_MAX];
    uint8_t  vendor_payload_len;
} disguise_t;

// In-RAM "current" disguise, shared by the control server and the WiFi code.
disguise_t *disguise_current(void);

void       disguise_init_defaults(void);  // load compile-time defaults into current
esp_err_t  disguise_load(void);           // current <- NVS (or defaults if absent)
esp_err_t  disguise_save(void);           // NVS <- current

// Merge a JSON control message into the current disguise. Unknown/omitted keys
// are left unchanged. Recognised keys:
//   "bssid":"aa:bb:cc:dd:ee:ff", "beacon_interval":100, "tx_power":84,
//   "vendor_ie": false | {"oui":"00:11:22","payload_hex":"deadbeef"}
esp_err_t  disguise_merge_json(const char *json);

// Serialise the current disguise to a malloc'd JSON string (caller frees).
char      *disguise_to_json(void);

// Helper: parse "aa:bb:cc:dd:ee:ff" into 6 bytes. Returns ESP_OK on success.
esp_err_t  disguise_parse_mac(const char *str, uint8_t out[6]);
