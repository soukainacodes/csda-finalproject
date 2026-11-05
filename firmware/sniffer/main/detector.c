#include "detector.h"

#include <string.h>
#include <stdio.h>
#include <inttypes.h>
#include "esp_log.h"
#include "led_strip.h"

// The network we are protecting. Overridable at build time.
#ifndef DETECTOR_TARGET_SSID
#define DETECTOR_TARGET_SSID "Kaffi_FRI"
#endif
// Onboard WS2812 on the ESP32-S3-DevKitC-1. Change if your board wires it elsewhere.
#ifndef DETECTOR_LED_GPIO
#define DETECTOR_LED_GPIO 48
#endif

#define AP_SLOTS   10
#define IE_SLOTS   4                 // distinct beacon IE-fingerprints kept per BSSID
#define AP_TTL_US  (8 * 1000000LL)   // a BSSID / IE / jump counts as "live" for 8 s

// TSF monotonicity thresholds. A single AP's TSF advances in lock-step with our
// local clock, so within the 8 s window the two deltas agree to well under a
// millisecond even at tens of ppm of skew. A clone interleaves two unrelated
// timers, producing backward steps and jumps of seconds. These margins sit far
// above genuine drift and far below a clone's jumps.
#define TSF_BACK_US   2000LL         // a real TSF never steps back; >2 ms back = clone
#define TSF_JUMP_US   150000LL       // |d(tsf) - d(local)| over 0.15 s = two clocks

static const char *TAG = "detector";

typedef struct {
    uint8_t  bssid[6];
    int8_t   rssi;
    int64_t  last_us;                // last time this BSSID was heard (any frame)
    bool     used;
    // detector 2: IE-fingerprint multiplicity
    uint32_t ie_hash[IE_SLOTS];
    int64_t  ie_us[IE_SLOTS];        // last time each fingerprint was seen
    // detector 3: TSF monotonicity
    uint64_t last_tsf;
    int64_t  last_tsf_us;
    bool     have_tsf;
    int64_t  last_jump_us;           // last time a backward/large TSF step was seen (0 = none)
} ap_t;

static ap_t              s_aps[AP_SLOTS];
static bool              s_detected;
static led_strip_handle_t s_led;

static void led_show(bool detected)
{
    if (!s_led) return;
    if (detected) led_strip_set_pixel(s_led, 0, 60, 0, 0);   // red: twin on the air
    else          led_strip_set_pixel(s_led, 0, 0, 40, 0);   // green: clear
    led_strip_refresh(s_led);
}

void detector_init(void)
{
    led_strip_config_t sc = { .strip_gpio_num = DETECTOR_LED_GPIO, .max_leds = 1 };
    led_strip_rmt_config_t rc = { .resolution_hz = 10 * 1000 * 1000 };
    if (led_strip_new_rmt_device(&sc, &rc, &s_led) != ESP_OK) {
        s_led = NULL;
        ESP_LOGW(TAG, "no addressable LED on GPIO %d; detection still logs to serial", DETECTOR_LED_GPIO);
    }
    led_show(false);  // start green / clear
}

// Record one beacon IE-fingerprint for a BSSID slot, refreshing its last-seen
// time. A new fingerprint takes a free slot, else evicts the oldest.
static void ie_record(ap_t *ap, uint32_t ie_hash, int64_t ts_us)
{
    if (ie_hash == 0) return;
    int oldest = 0;
    for (int j = 0; j < IE_SLOTS; j++) {
        if (ap->ie_hash[j] == ie_hash) { ap->ie_us[j] = ts_us; return; }  // seen before
        if (ap->ie_hash[j] == 0) { ap->ie_hash[j] = ie_hash; ap->ie_us[j] = ts_us; return; }
        if (ap->ie_us[j] < ap->ie_us[oldest]) oldest = j;
    }
    ap->ie_hash[oldest] = ie_hash; ap->ie_us[oldest] = ts_us;             // evict oldest
}

void detector_observe(const char *ssid, const uint8_t bssid[6], int8_t rssi,
                      int64_t ts_us, uint32_t ie_hash, uint64_t tsf, bool is_beacon)
{
    if (strcmp(ssid, DETECTOR_TARGET_SSID) != 0) return;   // only the network we protect

    int slot = -1, slot_free = -1;
    for (int i = 0; i < AP_SLOTS; i++) {
        if (s_aps[i].used && memcmp(s_aps[i].bssid, bssid, 6) == 0) { slot = i; break; }
        if (!s_aps[i].used && slot_free < 0) slot_free = i;
    }
    if (slot < 0) {                     // new BSSID for the target SSID
        if (slot_free < 0) return;      // table full
        slot = slot_free;
        memset(&s_aps[slot], 0, sizeof(ap_t));
        memcpy(s_aps[slot].bssid, bssid, 6);
        s_aps[slot].used = true;
    }
    ap_t *ap = &s_aps[slot];
    ap->rssi = rssi;
    ap->last_us = ts_us;

    // Detectors 2 and 3 only trust beacons (probe responses legitimately vary).
    if (!is_beacon) return;

    ie_record(ap, ie_hash, ts_us);

    if (tsf != 0) {
        if (ap->have_tsf) {
            int64_t d_tsf = (int64_t)(tsf - ap->last_tsf);   // AP clock delta
            int64_t d_loc = ts_us - ap->last_tsf_us;         // our clock delta
            int64_t diff  = d_tsf - d_loc;
            if (d_tsf < -TSF_BACK_US || diff > TSF_JUMP_US || diff < -TSF_JUMP_US)
                ap->last_jump_us = ts_us;                    // two clocks under one BSSID
        }
        ap->last_tsf = tsf;
        ap->last_tsf_us = ts_us;
        ap->have_tsf = true;
    }
}

bool detector_tick(int64_t now_us)
{
    int  live = 0;
    bool any_spoofed = false, any_ie_mismatch = false, any_tsf_jump = false;

    for (int i = 0; i < AP_SLOTS; i++) {
        if (!s_aps[i].used) continue;
        if (now_us - s_aps[i].last_us > AP_TTL_US) { s_aps[i].used = false; continue; }
        live++;
        if (s_aps[i].bssid[0] & 0x02) any_spoofed = true;   // locally-administered = possibly spoofed

        int n_ie = 0;                                       // distinct recent beacon fingerprints
        for (int j = 0; j < IE_SLOTS; j++)
            if (s_aps[i].ie_hash[j] != 0 && now_us - s_aps[i].ie_us[j] <= AP_TTL_US) n_ie++;
        if (n_ie >= 2) any_ie_mismatch = true;              // two capability-sets, one BSSID

        if (s_aps[i].last_jump_us != 0 && now_us - s_aps[i].last_jump_us <= AP_TTL_US)
            any_tsf_jump = true;
    }

    bool detected = (live >= 2) || any_ie_mismatch || any_tsf_jump;
    if (detected == s_detected) return detected;            // no change, nothing to log
    s_detected = detected;
    led_show(detected);

    if (detected) {
        char reasons[112]; int ro = 0;
        if (live >= 2)        ro += snprintf(reasons + ro, sizeof(reasons) - ro, "%s\"second-bssid\"", ro ? "," : "");
        if (any_ie_mismatch)  ro += snprintf(reasons + ro, sizeof(reasons) - ro, "%s\"ie-mismatch\"", ro ? "," : "");
        if (any_tsf_jump)     ro += snprintf(reasons + ro, sizeof(reasons) - ro, "%s\"tsf-jump\"", ro ? "," : "");
        if (any_spoofed)      ro += snprintf(reasons + ro, sizeof(reasons) - ro, "%s\"spoofed-mac\"", ro ? "," : "");

        printf("{\"k\":\"detect\",\"state\":\"DETECTED\",\"ssid\":\"%s\",\"live_bssids\":%d,"
               "\"t\":%" PRId64 ",\"reasons\":[%s],\"bssids\":[",
               DETECTOR_TARGET_SSID, live, now_us, reasons);
        bool first = true;
        for (int i = 0; i < AP_SLOTS; i++) {
            if (!s_aps[i].used) continue;
            printf("%s{\"b\":\"%02x:%02x:%02x:%02x:%02x:%02x\",\"rssi\":%d}", first ? "" : ",",
                   s_aps[i].bssid[0], s_aps[i].bssid[1], s_aps[i].bssid[2],
                   s_aps[i].bssid[3], s_aps[i].bssid[4], s_aps[i].bssid[5], s_aps[i].rssi);
            first = false;
        }
        printf("]}\n");
    } else {
        printf("{\"k\":\"detect\",\"state\":\"CLEAR\",\"ssid\":\"%s\",\"t\":%" PRId64 "}\n",
               DETECTOR_TARGET_SSID, now_us);
    }
    return detected;
}
