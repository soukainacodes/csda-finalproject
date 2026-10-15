// Parse a captured 802.11 management frame (beacon / probe response) and print
// one JSON line describing it to the console (which the laptop reads over USB).
// The Watcher does the actual feature engineering; the sniffer just reports the
// raw observable fields faithfully, including the ORDERED list of IE tag ids,
// which is a key fingerprint for distinguishing the real router from the twin.
#pragma once

#include <stdint.h>

void beacon_parse_and_print(const uint8_t *frame, int len,
                            int8_t rssi, uint8_t channel, int64_t ts_us);
