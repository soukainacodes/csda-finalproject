// The over-the-air half of AL-GHUL: bring up SoftAP (the clone) + STA (the
// uplink the relay rides on), and apply a disguise. No deauth, no jamming here
// or anywhere: this module only configures beacons and an uplink.
#pragma once

#include "esp_err.h"
#include "esp_netif.h"
#include "esp_wifi_types.h"   // wifi_auth_mode_t
#include "disguise.h"

esp_err_t    wifi_twin_init(void);                         // after netif + event loop
esp_err_t    wifi_twin_start(const disguise_t *d);         // configure + start AP+STA
esp_err_t    wifi_twin_apply_disguise(const disguise_t *d);// stop, reconfigure, start

// Security-mode experiment: switch the auth mode the clone ADVERTISES, so one
// firmware can impersonate every personal WiFi mode and we can measure which a
// victim still joins. Causes a brief AP restart (serial control survives it).
esp_err_t    wifi_twin_set_authmode(wifi_auth_mode_t mode, bool pmf_required);
const char  *wifi_twin_authmode_name(void);                // human label for logs

esp_netif_t *wifi_twin_ap_netif(void);
esp_netif_t *wifi_twin_sta_netif(void);
