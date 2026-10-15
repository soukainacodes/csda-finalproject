// The over-the-air half of AL-GHUL: bring up SoftAP (the clone) + STA (the
// uplink the relay rides on), and apply a disguise. No deauth, no jamming here
// or anywhere: this module only configures beacons and an uplink.
#pragma once

#include "esp_err.h"
#include "esp_netif.h"
#include "disguise.h"

esp_err_t    wifi_twin_init(void);                         // after netif + event loop
esp_err_t    wifi_twin_start(const disguise_t *d);         // configure + start AP+STA
esp_err_t    wifi_twin_apply_disguise(const disguise_t *d);// stop, reconfigure, start

esp_netif_t *wifi_twin_ap_netif(void);
esp_netif_t *wifi_twin_sta_netif(void);
