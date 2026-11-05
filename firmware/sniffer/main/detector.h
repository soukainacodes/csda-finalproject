// On-board evil-twin detector for the Watcher (second ESP32).
//
// The sniffer feeds every beacon/probe-response here. We keep a short-lived
// table of the BSSIDs advertising the TARGET SSID and run three detectors live:
//
//   1. rule-1 (second BSSID): the target SSID heard from >= 2 BSSIDs at once.
//      Catches a twin that uses its own MAC, blind to a twin that clones the
//      real BSSID exactly.
//   2. IE-fingerprint multiplicity: under ONE BSSID we should see one stable
//      beacon capability-set. Two distinct sets under the same BSSID means two
//      radios sharing an identity = an exact clone. (Caught Scenario B offline.)
//   3. TSF monotonicity: one real AP's 64-bit TSF timer rises smoothly with our
//      local clock. A backward step or a large jump means two independent clocks
//      under one BSSID = an exact clone. (Cleanest offline detector on B.)
//
// Detectors 2 and 3 catch the exact-BSSID clone that rule-1 cannot see. All
// signals age out, so the LED returns to green once the twin leaves the air.
//
// On a state change we drive the status LED (green = clear, red = detected) and
// print one JSON line (with the reasons that fired) so the laptop can compute
// detection rate, time-to-detect and false-positive rate.
//
// Passive and receive-only, like the rest of the sniffer. Lab use only.
#pragma once

#include <stdint.h>
#include <stdbool.h>

void detector_init(void);                               // bring up the status LED

// One frame for the target SSID. ie_hash is a fingerprint of the beacon's IE
// tag sequence (0 if unknown), tsf is the AP's advertised 64-bit timer, and
// is_beacon distinguishes beacons (stable IEs/TSF) from probe responses.
void detector_observe(const char *ssid, const uint8_t bssid[6], int8_t rssi,
                      int64_t ts_us, uint32_t ie_hash, uint64_t tsf, bool is_beacon);

bool detector_tick(int64_t now_us);                     // expire, evaluate, LED + log; returns detected
