// The transparent relay: NAT between the SoftAP (phone side) and the STA uplink
// (internet side), so a client on the clone gets working internet through
// AL-GHUL's own uplink. This is ordinary WiFi-repeater behaviour. AL-GHUL does
// NOT inspect, log, or alter client payloads; H2 only requires that the internet
// keeps working, not that any traffic content is captured.
#pragma once

#include "esp_err.h"
#include "esp_netif.h"

esp_err_t napt_relay_enable(esp_netif_t *ap_netif);
void      napt_relay_set_ap_dns_from_sta(esp_netif_t *ap_netif, esp_netif_t *sta_netif);

// DANGER DEMO ONLY: advertise the twin itself as the DNS server and log every
// domain the victim looks up (see dns_spy.h). Lab-only, educational.
void      napt_relay_enable_dns_spy(esp_netif_t *ap_netif, esp_netif_t *sta_netif);
