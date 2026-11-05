# On-board Watcher live detection of an exact-BSSID clone (2026-11-05, own lab)

Live hardware demonstration that the second ESP32 (the Watcher) now catches the
exact-BSSID clone in real time, which the BSSID-count rule (rule-1) cannot see.

## Setup
- Watcher: ESP32-S3 sniffer, COM15, running the 3-detector firmware (firmware/sniffer).
  Detectors on board: rule-1 (BSSID count), IE-fingerprint multiplicity, TSF monotonicity.
  LED: green = clear, red = detected. All signals age out over 8 s (so it recovers).
- Twin: AL-GHUL ESP32-S3, COM18, cloning the real BSSID aa:d0:43:06:46:e1 (STATUS confirmed
  {"bssid":"aa:d0:43:06:46:e1","beacon_interval":100,"tx_power":40,"vendor_ie":false}).
- Real AP: laptop Windows Mobile Hotspot "Kaffi_FRI", same BSSID aa:d0:43:06:46:e1 (ch 6).
- Scenario B live: one BSSID on the air, two independent radios under it.

## Captured serial transitions (COM15, verbatim fields)
```
[13.1s] CLEAR
[23.1s] DETECTED  reasons=['ie-mismatch','tsf-jump','spoofed-mac']  live_bssids=1  bssids=[{aa:d0:43:06:46:e1, rssi -53}]
[48.1s] CLEAR
[55.1s] DETECTED  reasons=['ie-mismatch','tsf-jump','spoofed-mac']  live_bssids=1  bssids=[{aa:d0:43:06:46:e1, rssi -22}]
```
(CLEAR/DETECTED toggled by switching the real hotspot off and on during the window.)

## What it proves
- At DETECTED, live_bssids = 1: only one BSSID is present, so rule-1 (second-bssid) does NOT
  fire. The detection came only from the new detectors:
    ie-mismatch : two distinct beacon IE-fingerprints under the one BSSID (real laptop set +
                  twin ESP32 set) = two emitters sharing an identity.
    tsf-jump    : the advertised 64-bit TSF timer steps backward / jumps under the one BSSID
                  = two independent clocks.
- CLEAR when the twin is alone (hotspot off): a lone AP using the cloned identity does not
  false-trigger. Correct control behaviour.
- Red -> green -> red: signals age out in 8 s, so the Watcher recovers when the second radio
  leaves. Not a latched one-shot.
- spoofed-mac also fires because the Windows Mobile Hotspot's BSSID aa:.. is a locally-
  administered MAC (first-octet bit 0x02 set). A true but weak extra signal; the headline is
  ie-mismatch + tsf-jump.

## Significance
The naive scanner (count BSSIDs per SSID) is blind to an exact-BSSID clone. This on-board
detector, on a ~5 USD ESP32, catches it live from passive beacons alone, using an IE
fingerprint and the AP clock. This is the hardware counterpart to the offline result in
master-detector-comparison.md (Scenario B), now shown running on the device with the LED.

## On-board A/B/C sweep (the DEVICE decides each scenario, saved to files)

Run with watcher_onboard.py, which logs the Watcher's own {"k":"detect"} verdict live and
saves the raw serial to a file per scenario (fixes the earlier not-saved-to-file gap).

| Scenario | Setup | Device verdict | reasons (device) | live_bssids | raw file |
|---|---|---|---|---|---|
| A | twin on 02:a1 + real aa:d0 | DETECTED | second-bssid, spoofed-mac | 2 | watcher-onboard-raw-A-20261105-123817.jsonl |
| B | twin clones aa:d0 + real aa:d0 | DETECTED | ie-mismatch, tsf-jump, spoofed-mac | 1 | watcher-onboard-raw-B-20261105-123650.jsonl |
| C | single emitter (hotspot off) | CLEAR | none | - | watcher-onboard-raw-C-20261105-123946.jsonl |

Reading: the device catches the twin in BOTH the different-BSSID case (A, via rule-1) and the
exact-clone case (B, one BSSID, via ie-mismatch + tsf-jump which rule-1 cannot see), and does
not false-alarm on a lone AP (C: dropped to CLEAR the moment the second emitter left).
Each scenario also has a watcher-onboard-sum-{A,B,C}-*.json with the transitions and verdict.
Capture tool: experiments/watcher_onboard.py (COM15, dtr/rts low, passive).

## Provenance
- Firmware source: firmware/sniffer/main/detector.c (+ detector.h), beacon_parse.c feeds
  ie_hash + tsf + is_beacon. Built clean (idf.py build, exit 0), flashed to COM15 (hash verified).
- Offline corroboration: experiments/master-detector-comparison.md, detector-comparison-results.md.
- Code is not yet committed to git (firmware/ + gateway/ still uncommitted as of this session).
