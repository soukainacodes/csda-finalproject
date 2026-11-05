# On-board Watcher results, full A/B/C sweep with timing (2026-11-05, own lab)

The ESP32-S3 Watcher deciding LIVE, on the device, for every scenario. Not offline Python:
these are the {"k":"detect"} verdicts the firmware itself emitted. Every run saved to a file.

## Setup (verified clean)
- Watcher: ESP32-S3, COM15, 3-detector firmware (rule-1 + IE-fingerprint + TSF monotonicity),
  channel-hopping sniff, LED green=clear / red=detected, all signals age out over 8 s.
- Twin: AL-GHUL ESP32-S3, COM18, BSSID set over serial per scenario.
- Real AP: PC Windows Mobile Hotspot "Kaffi_FRI". Its virtual-adapter MAC is AA-D0-43-06-46-E1,
  so aa:d0:43:06:46:e1 IS the PC hotspot (confirmed, not the S24 phone).
- S24 phone hotspot: OFF for this sweep. Audit of all raw logs: the only Kaffi_FRI BSSIDs ever
  seen are aa:d0 (PC hotspot) and 02:a1 (twin). No third emitter ever polluted a measurement.

## Results (device verdict + time-to-detect)

| Scenario | Setup | Device verdict | reasons (from device) | live_bssids | time-to-detect | raw file |
|---|---|---|---|---|---|---|
| A | twin 02:a1 + real aa:d0 (two BSSIDs) | DETECTED | second-bssid, spoofed-mac | 2 | 7 s (also 20 s in a 2nd run) | watcher-onboard-raw-A-20261105-124953.jsonl |
| B | twin clones aa:d0 + real aa:d0 (exact clone) | DETECTED | ie-mismatch, tsf-jump, spoofed-mac | 1 | 6-37 s (hopping-dependent) | watcher-onboard-raw-B-20261105-125100.jsonl |
| C | single emitter (twin alone, real AP off) | CLEAR | none | 1 | n/a (no detection, correct) | watcher-onboard-raw-C-20261105-125911.jsonl |

Key point: B is the case rule-1 is BLIND to (live_bssids=1, one BSSID). The device catches it
only through the new detectors (ie-mismatch + tsf-jump). A is the easy different-BSSID case
(rule-1). C is the no-false-alarm control.

## Timing detail (B, 150 s continuous run: watcher-onboard-raw-Btiming-20261105-125305.jsonl)

Transitions (s): DETECTED 6.1, CLEAR 47.1, DETECTED 49.1, CLEAR 86.1, DETECTED 93.1, CLEAR 140.1.
- Time-to-detect (first acquire): 6.1 s this run.
- Re-acquire after a brief clear: 2.0 s and 7.0 s.
- Detection hold once acquired: 41 s, 37 s, 47 s (keeps seeing the twin often enough).
- Detection coverage: ~125 s of 150 s = ~83 % of the time DETECTED; clear only in short 2-7 s gaps.
- Clear-latency (time to drop to CLEAR after the second emitter leaves): ~8 s, = the detector's
  8 s evidence TTL by design (seen as the DETECTED->CLEAR steps and in scenario C/A tails).

## How to read the times honestly
- A detects in seconds because rule-1 fires the instant two BSSIDs are both seen.
- B's acquire time varies (6-37 s across runs) because BOTH the twin and the Watcher channel-hop,
  so the Watcher must coincide on-channel with the twin AND the real AP within one 8 s window.
  Once acquired it holds ~83 % of the time. A channel-locked Watcher (sit on ch 6, the real AP's
  channel) would cut B's acquire time sharply; left as a stated improvement, not done here.

## Files (this sweep, all S24-off, aa:d0=PC hotspot)
raw: watcher-onboard-raw-{A,B,C,Btiming}-2026110512*.jsonl
sum: watcher-onboard-sum-{A,B,C,Btiming}-2026110512*.json  (transitions + verdict per run)
capture tool: watcher_onboard.py   twin control: STATUS/disguise over COM18
Earlier same-day on-board runs (also valid, audited clean): *-2026110512{3,4}*.jsonl
Offline corroboration: master-detector-comparison.md, detector-comparison-results.md.
