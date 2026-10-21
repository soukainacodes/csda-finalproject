// AL-GHUL compile-time configuration.
//
// SCOPE REMINDER: this firmware runs ONLY on Soukaina's own ESP32-S3, cloning
// HER OWN home router on HER OWN isolated lab network, with HER OWN phone as the
// only client. No deauth, no jamming: the twin only broadcasts and relays. The
// research purpose is to generate a controllable twin so the Watcher (the ML
// detector on the laptop) can be trained and measured. See docs/ETHICS.md.
//
// Fill in your own router's details below before flashing. These are defaults;
// they can also be overridden at runtime over the HTTP control interface and are
// persisted in NVS.
#pragma once

// ---- Target network to clone (YOUR OWN router) -----------------------------
// The twin advertises this SSID. The STA uplink also connects to this SSID so
// the relay has a working internet path. Because it is your own network, you
// know the passphrase, so the clone can present the same credentials and your
// phone roams onto it seamlessly (this is what makes H1/H2 measurable).
#define ALGHUL_TARGET_SSID        "Kaffi_FRI"
#define ALGHUL_TARGET_PSK         "bestcoffee"   // "" = open network

// Real router BSSID (the STA uplink locks to this so AL-GHUL uses the REAL AP as
// its uplink and not, accidentally, itself). Format: 6 bytes.
// Find it with:  (Windows)  netsh wlan show interfaces   -> "BSSID".
#define ALGHUL_UPLINK_BSSID       { 0xca, 0xf0, 0x57, 0xfc, 0x30, 0x00 }  // all-zero = don't lock; set to your real AP's BSSID

// ---- Default disguise (round 0) --------------------------------------------
// The twin's own AP BSSID. Locally-administered, unicast (second hex digit 2/6/
// A/E, last bit of first byte = 0). The arms-race attacker will mutate this.
#define ALGHUL_DEFAULT_AP_BSSID   { 0x02, 0xA1, 0x00, 0x00, 0x00, 0x01 }

// Beacon interval in TU (1 TU = 1.024 ms). 100 is the common default; the
// attacker varies it as a timing-fingerprint knob.
#define ALGHUL_DEFAULT_BEACON_TU  100

// Max TX power in 0.25 dBm steps (8..84). 84 == 21 dBm == "out-signal" loud.
#define ALGHUL_DEFAULT_TX_POWER   84

// ---- Danger demo (EDUCATIONAL, lab-only) -----------------------------------
// 1 = enable the "what the attacker sees" demonstration: AL-GHUL advertises
// itself as the DNS server and LOGS every domain the connected phone looks up
// (names only, never payloads), to show that a device on the twin leaks its whole
// browsing map even over HTTPS. Keep this 0 in the benign/relay build. Runs ONLY
// on the student's own devices in the isolated lab. See docs/ETHICS.md.
#define ALGHUL_DANGER_DEMO        1

// ---- Control plane ---------------------------------------------------------
#define ALGHUL_CONTROL_PORT       80         // HTTP control + OTA receive
#define ALGHUL_AP_MAX_CONN        4
#define ALGHUL_NVS_NAMESPACE      "alghul"

// Shared secret that authenticates the dangerous commands (/kill, /ota). The
// request must carry ?token=<this>. This is what makes the kill an AUTHENTICATED
// command the board is built to obey, not something any client on the AP can
// trigger. Change it to your own secret.
#define ALGHUL_CONTROL_TOKEN      "ghoul-begone-2026"
