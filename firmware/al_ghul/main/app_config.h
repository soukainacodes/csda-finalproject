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
// All-zero here because the uplink is now a UNIQUELY named backhaul (below), so
// there is no ambiguity to resolve with a BSSID lock.
#define ALGHUL_UPLINK_BSSID       { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }  // all-zero = don't lock

// ---- Attacker backhaul (the twin's own uplink) -----------------------------
// The STA uplink connects to THIS network, the attacker's gateway laptop, NOT to
// the cloned SSID above. Separating the uplink from the advertised clone means the
// victim only ever sees one "Kaffi_FRI" (the twin's), which makes the gateway
// capture deterministic, and it models a real evil twin that routes its victims
// out through its own independent backhaul. The laptop runs this SSID (Windows
// Mobile Hotspot) and all victim traffic is captured on that laptop adapter.
#define ALGHUL_UPLINK_SSID        "ALGHUL_UP"
#define ALGHUL_UPLINK_PSK         "backhaul2026"

// ---- Default disguise (round 0) --------------------------------------------
// The twin's own AP BSSID. Locally-administered, unicast (second hex digit 2/6/
// A/E, last bit of first byte = 0). The arms-race attacker will mutate this.
#define ALGHUL_DEFAULT_AP_BSSID   { 0x02, 0xA1, 0x00, 0x00, 0x00, 0x01 }

// ---- Measurement mode (detector study) -------------------------------------
// A real evil twin sits on the victim's channel and beacons continuously. In
// this lab the twin's uplink is dead, so its STA hops while scanning and the AP
// beacon is sparse, which starves the channel-dependent detectors. Set to 1 to
// run AP-only, pinned to ALGHUL_MEASURE_CHANNEL, so the twin beacons steadily
// co-channel with the real AP (relay/uplink is irrelevant to the defence study).
#define ALGHUL_MEASURE_STABLE     0
#define ALGHUL_MEASURE_CHANNEL    6

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

// ---- Status LED ------------------------------------------------------------
// Onboard addressable RGB LED (WS2812). GREEN = clone empty (no victim joined),
// RED = at least one device is on the clone. A glanceable "someone took the bait"
// light for the live demo. GPIO48 is the onboard WS2812 on the ESP32-S3-DevKitC-1;
// change it if your board wires the LED to a different pin.
#define ALGHUL_LED_GPIO           48

// ---- Control plane ---------------------------------------------------------
#define ALGHUL_CONTROL_PORT       80         // HTTP control + OTA receive
#define ALGHUL_AP_MAX_CONN        4
#define ALGHUL_NVS_NAMESPACE      "alghul"

// Shared secret that authenticates the dangerous commands (/kill, /ota). The
// request must carry ?token=<this>. This is what makes the kill an AUTHENTICATED
// command the board is built to obey, not something any client on the AP can
// trigger. Change it to your own secret.
#define ALGHUL_CONTROL_TOKEN      "ghoul-begone-2026"
