# Detector comparison, measured results (2026-11-05, own lab, 2.4 GHz)

> Note: the canonical detector comparison referenced by the README and the report is
> [`master-detector-comparison.md`](master-detector-comparison.md). This file is a
> companion with the same runs, organised results only.

Organised results only, no narrative.

Ground truth: the AL-GHUL twin, reconfigured over serial.
Real AP: laptop Mobile Hotspot "Kaffi_FRI", bssid aa:d0:43:06:46:e1 (always-on, chosen
because the phone hotspot kept idling its beacons off).
Watcher: ESP32-S3 sniffer on COM15, channel-hopping 1..13, 300 ms/channel.

Detectors compared:
- RULE-1  : target SSID heard from >= 2 BSSIDs = twin present. On-board, instant.
- CLOCK-SKEW : per-BSSID fit of the AP's TSF clock vs our local receive time. A high
  single-line fit RMSE means two unrelated clocks under one BSSID = a clone (Jana & Kasera 2010).
- ML (RandomForest, watcher/src) : radio/timing fingerprint, BSSID excluded to avoid leakage.

## Results table

| Scenario | Setup | RULE-1 | CLOCK-SKEW | ML (expected) |
|---|---|---|---|---|
| A | twin + real, DIFFERENT BSSIDs | DETECT (2 bssids, det_rate 50%, ttd 0 s) | DETECT (2 distinct skews) | DETECT (fingerprint) |
| B | twin CLONES real bssid aa:d0 | MISS (1 bssid, 0%) | DETECT (fit RMSE 7.3e10 us) | DETECT (fingerprint, bssid-independent) |
| C | single AP only (control) | CLEAR (1 bssid) | CLEAR (clean fit) | n/a (twin still present) |

## Clock-skew fit RMSE, the discriminator (microseconds)

| condition | fit RMSE |
|---|---|
| genuine single clock (A twin) | 24.0 |
| genuine single clock (A real/laptop) | 79.0 |
| genuine single clock (C twin) | 13.0 |
| CLONED bssid, two clocks mixed (B) | 72,617,788,294.5 |

Separation genuine-vs-clone is ~9 orders of magnitude; any threshold near 1e3 us
classifies perfectly.

## Per-BSSID clock skew (ppm)

| run | bssid | skew ppm | note |
|---|---|---|---|
| A | 02:a1:00:00:00:01 (twin) | -4.0 | |
| A | aa:d0:43:06:46:e1 (real) | -31.0 | 27 ppm from the twin, distinct radios |
| C | aa:d0 (twin, cloned id) | -4.1 | matches twin's own skew, consistent |
| B | aa:d0 (mixed) | 1.6e7 (meaningless) | fit invalid, two clocks |

## Per-detector summary

- RULE-1: detection_rate A=50%, B=0%, C=clear. time-to-detect A=0 s. False positives: none.
  Weakness: BLIND to an exact-BSSID clone (B).
- CLOCK-SKEW: detects A (distinct skews) AND B (exploded fit); clear in C. Catches the case
  rule-1 misses. Cost: needs enough beacons per BSSID to fit, so slower, and channel-hopping
  reduces the sample count.
- ML: BSSID-independent fingerprint; expected to catch A and B like clock-skew. A clean
  real-only false-positive run is future work (could not power the twin off this session).

## Three more detectors, run offline on the same captures (detector_analysis.py)

| Detector | A (diff bssid) | B (CLONE) | C (single AP) |
|---|---|---|---|
| RSSI-bimodality | flag (artifact) | DETECT (sep 39 dB, minor 0.17) | clear |
| multi-channel | flag (twin hops) | DETECT (ch 1,2,6) | flag (twin hops) |
| TSF-jump | clear | DETECT (32/164 big jumps, 16 backward) | clear |

Honest assessment of the new three:
- TSF-JUMP: cleanest. Fires only on the clone (B), silent on A and C. Catches exactly
  the case rule-1 misses, with no false positives seen. Best of the new three.
- RSSI-BIMODALITY: detects the clone (39 dB gap = two locations) but has an artifact,
  saturated readings near -1 dB produced a spurious 73 dB split on the twin in A. Needs
  outlier trimming to be trustworthy.
- MULTI-CHANNEL: detects the clone but is confounded, it really keys on "this BSSID hops
  channels", which the twin does whenever it scans for an uplink, so it also flags the twin
  alone (C). A behavioural tell, not a clean clone detector.

Conclusion (five detectors): no single cheap detector covers everything. Rule-1 handles the
easy different-BSSID twin and is blind to the exact-BSSID clone; the clock-based detectors
(clock-skew, TSF-jump) are what catch the clone; RSSI and channel heuristics each carry their
own false-positive profile. The clone case (B) is caught only by the physical-layer detectors.

## Four refinement detectors, run offline on the same captures (detector_analysis2.py)

| Detector | A (diff bssid) | B (CLONE) | C (single emitter) |
|---|---|---|---|
| IE-fingerprint | cross-BSSID Jaccard 0.27 (radios differ) | DETECT (2 distinct beacon IE-sets under 1 BSSID) | clear (1 IE-set) |
| beacon-rate | no flag (ratio 0.67) | no flag (ratio 1.0) | no flag (ratio 0.67) |
| inter-beacon timing | no sub-interval gaps (0/8) | no sub-interval gaps (0/47) | no gaps (0/3) |
| ENSEMBLE score (0..1) | 0.40 -> DETECT | 0.80 -> DETECT | 0.03 -> CLEAR |

Honest assessment of the refinement four:
- IE-FINGERPRINT: the standout. Catches the exact-BSSID clone (B) that rule-1 is blind to,
  by counting distinct beacon IE-sets under one BSSID (2 = two emitters: the real laptop's
  rich set incl. vendor OUI 00:e0:4c, plus the twin's sparse ESP32 set). No false positive on
  C. In A the cross-BSSID IE Jaccard (0.27) independently confirms two different radios. This
  is "the ML's input without the ML", and it recovers the clone case cheaply and transparently.
- BEACON-RATE: did not fire in any scenario. The Watcher channel-hops, so the "two emitters
  under one BSSID => ~2x beacons" signal never materialises (the two trains are rarely on the
  sniffer's current channel together). Needs a CHANNEL-LOCKED capture to be usable. Honest
  negative, same precondition as the sequence-number detector.
- INTER-BEACON TIMING: also did not fire, same cause: hopping means the sniffer seldom catches
  both interleaved trains within one dwell burst, so no sub-interval (< 0.7*bi) gap cluster
  appears. Needs a channel-locked capture. Honest negative.
- ENSEMBLE: the natural conclusion detector. One weighted score over {IE-multiplicity,
  clock-skew RMSE, TSF-backward, beacon-rate, inter-beacon, RSSI-bimodality, multi-channel}
  plus the SSID-level second-BSSID rule. Scores A=0.40, B=0.80, C=0.03: DETECT/DETECT/CLEAR
  with clean margin. It catches B (which rule-1 misses) because it folds in the IE + clock
  signals. multi_channel is deliberately down-weighted (0.03) so a lone hopping twin (C) does
  not trip it, confirmed: C scores 0.03, below the 0.30 threshold.

Cross-check bonus: C's single IE-set matches the twin's A-signature, corroborating the
clock-skew identification that C's lone emitter was the twin (real AP off), not the laptop.

## Still to do
- SEQUENCE-NUMBER discontinuity: code-complete (sniffer firmware + detector_analysis.py), but
  MEASUREMENT pending. Needs the SN firmware flashed and a CHANNEL-LOCKED recapture of A/B/C
  (these captures predate the SN firmware: they carry tsf but no sn field).
- A channel-locked recapture would also let beacon-rate and inter-beacon timing be measured
  properly (both are blind on the current hopping captures).
- ML (RandomForest) false-positive baseline against a twin-free network (needs the twin off).

## Files
raw: watcher-raw-{A,B,C}-*.jsonl   per-run: watcher-summary-{A,B,C}-*.json
offline: detector_analysis.py  (RSSI-bimodality, multi-channel, TSF-jump, seq-number)
offline: detector_analysis2.py (IE-fingerprint, beacon-rate, inter-beacon, ensemble)

## Honest limits
Single Watcher, single real AP and single twin, 2.4 GHz, own devices. Detection rates
reflect channel-hopping sampling, not a tuned detector. Rule-1 50% in A is the hopping
duty cycle, not a weakness of the rule. The ML leg is characterised in the main project;
only its false-positive baseline against a twin-free network remains to run.
