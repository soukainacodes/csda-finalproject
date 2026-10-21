// DANGER-DEMO ONLY. A DNS logger for the "what the attacker sees" demonstration.
//
// When the danger demo is enabled, AL-GHUL advertises ITSELF as the DNS server to
// its SoftAP clients and runs this forwarder: it logs every domain the victim
// phone looks up (over the USB console as "DNSSPY <name>"), then forwards the
// query upstream and returns the real answer, so browsing still works. It proves
// that a connected device leaks its entire browsing map even though the traffic
// itself is HTTPS-encrypted. It reads names only, never payloads, and runs ONLY
// on the student's own lab devices. The benign build does not include it.
#pragma once

#include <stdint.h>

// upstream_ip: the real DNS to forward to (IPv4, network byte order).
void dns_spy_start(uint32_t upstream_ip);
