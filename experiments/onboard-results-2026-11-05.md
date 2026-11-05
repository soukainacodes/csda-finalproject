# On-board Watcher results, full sweep + timing (2026-11-05, own lab)

The ESP32-S3 Watcher deciding LIVE, on the device, across every case. These are the
{"k":"detect"} verdicts the firmware itself emits; every run saved to its own file.
Real AP = PC Mobile Hotspot "Kaffi_FRI" aa:d0:43:06:46:e1 (adapter MAC confirmed). S24 off.
Audit: every capture only ever shows aa:d0 (real) + 02:a1 (twin); no stray emitter.

## 1. Core scenarios A / B / C (time-to-detect)

| Scenario | Setup | Device verdict | reasons | live_bssids | time-to-detect | raw file |
|---|---|---|---|---|---|---|
| A | twin 02:a1 + real aa:d0 (two BSSIDs) | DETECTED | second-bssid, spoofed-mac | 2 | ~7-19 s | watcher-onboard-raw-A-20261105-132518.jsonl |
| B | twin clones aa:d0 + real aa:d0 (exact clone) | DETECTED | ie-mismatch, tsf-jump, spoofed-mac | 1 | ~6-37 s | watcher-onboard-raw-B-20261105-132355.jsonl |
| C | single emitter (real AP off) | CLEAR | none | 1 | n/a (correct) | watcher-onboard-raw-C-20261105-125911.jsonl |

B is the case rule-1 is blind to (live_bssids=1): caught only by ie-mismatch + tsf-jump.
Timing notes: A detects in seconds (needs 2 BSSIDs once). B's acquire time varies because both
the twin and the Watcher channel-hop; once acquired it holds ~83% of the time (150 s timing run
watcher-onboard-raw-Btiming-20261105-125305.jsonl). Clear-latency after a radio leaves ~8 s (TTL).

## 2. Security-mode sweep (does detection survive the twin's advertised mode?)

| Twin mode | Device verdict | reasons | raw file |
|---|---|---|---|
| WPA2-PSK | DETECTED | ie-mismatch, tsf-jump | watcher-onboard-raw-SecWPA2-20261105-133813.jsonl |
| WPA2-PSK + PMF | DETECTED | ie-mismatch, tsf-jump | watcher-onboard-raw-SecPMF-20261105-133950.jsonl |
| WPA3-SAE | not measurable | (twin beacon not capturable, see note) | watcher-onboard-raw-SecWPA3-20261105-134334.jsonl |

Detection is mode-independent for WPA2 and WPA2+PMF (the detectors read beacons, which exist in
every mode). WPA3 note: on this ESP32-S3 / ESP-IDF 5.2.8 the twin's beacon could not be captured
in WPA3-SAE mode across repeated 90-120 s windows (the twin went silent, same as the vendor-IE
case below); this is a twin-firmware limitation, not a detector failure.

## 3. Evasion asymmetry (which detectors are evadable vs fundamental)

Attempt: make the twin advertise the real AP's Microsoft vendor IE (OUI 00:50:f2) to mimic it.
Result: enabling the vendor IE BROKE the twin's beacon on this firmware, it went off the air
(watcher-onboard-raw-EvVendor-*; only the real AP heard). Turning it off restored beaconing
(watcher-onboard-raw-EvBaseline-20261105-132652.jsonl: DETECTED ie-mismatch + tsf-jump).
- Finding: config/identity tells (IE set, vendor IE) are evadable in principle, but the twin on
  this hardware could not even apply this one without self-destructing; and its base IE set still
  differs from the Windows AP, so ie-mismatch keeps firing.
- tsf-jump / clock-skew are fundamentally NOT evadable: the twin cannot fake another radio's
  hardware TSF clock. That asymmetry is the point: kill the config tells and the physical-clock
  detector still stands.

## 4. Channel-locked run (the three detectors that were blind while hopping)

Setup: Watcher locked to ch6 (SNIFFER_LOCK_CHANNEL=6) AND twin pinned to ch6, AP-only
(ALGHUL_MEASURE_STABLE=1), so both emitters beacon continuously co-channel, as a real evil twin
sitting on the victim's channel would. Capture: watcher-onboard-raw-ChLock6-20261105-140320.jsonl
(2297 beacons, 120 s). Analysis: analyze_chlock.py.

| Detector | Measured | Fires? |
|---|---|---|
| sequence-number | big back-steps 1127/2296, frac 0.49 | YES (two independent SN counters interleaved) |
| beacon-rate | 19.1 Hz vs 9.8 nominal, ratio 2.01 | YES (exactly double = two emitters, one BSSID) |
| inter-beacon timing | sub-interval frac 0.98 (2246/2296) | YES (two beacon trains interleaving) |

These were blind on the earlier hopping captures only because the twin grazed ch6 briefly. With
the twin pinned co-channel they detect the clone decisively. Earlier hopping ch6-lock (twin not
pinned) stayed at 9.8 Hz / frac 0.00 (watcher-onboard-raw-ChLock6-20261105-134939.jsonl), which is
itself the honest control: the detectors need both radios continuously on-channel.

## Full detector x case status
Every detector now has a measured result. rule-1 (A), ie-mismatch + tsf-jump (B, all modes),
clear on C, sequence-number + beacon-rate + inter-beacon (channel-locked), evasion + security-mode
characterised. Remaining honest limits: WPA3 twin-beacon capture, and the single-Watcher / single
real-AP / single-twin scope.

## Device state after this session
Devices are currently flashed in MEASUREMENT mode: Watcher ch6-locked, twin AP-only pinned ch6.
Source flags are reverted to default-off (SNIFFER_LOCK_CHANNEL 0, ALGHUL_MEASURE_STABLE 0), so a
rebuild+reflash restores normal behavior (hopping Watcher, APSTA relay twin).

## Files
raw + per-run sum: watcher-onboard-{raw,sum}-*.jsonl/json   capture tool: watcher_onboard.py
channel-lock analysis: analyze_chlock.py   offline detectors: detector_analysis.py / _analysis2.py

## Detection-latency distribution (addresses the single-run point-estimate critique)
Across 9 logged clone-detection acquisitions (clear-to-detect gaps, all B-type on-board runs):
samples = [2,2,2,3,3,6,6,7,10] s -> n=9, median 3 s, mean 4.6 s, range 2-10 s, stdev 2.7 s.
The longer per-run "first-encounter" times (6-37 s) are the hopping Watcher's channel-sampling
luck (time to first coincide on the clone's channel), not detection speed. Reported as a
distribution, not a point estimate.
