// USB serial control plane. The laptop sends one line per command over the S3's
// USB cable (far more reliable than WiFi, which drops whenever the twin changes):
//   {"beacon_interval":150,...}  -> apply a disguise patch (same JSON as /disguise)
//   STATUS                        -> print the current disguise
//   PING                          -> PONG
// Replies are printed back on the same USB console.
#pragma once

#include "esp_err.h"

esp_err_t serial_control_start(void);
