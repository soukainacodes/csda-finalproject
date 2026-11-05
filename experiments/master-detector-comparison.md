# Master detector comparison, all scenarios x all detectors (measured, 2026-11-05)

Own lab, 2.4 GHz. Watcher = ESP32-S3 sniffer (COM15), channel-hopping 1..13 @ ~300 ms.
Real AP = laptop Mobile Hotspot "Kaffi_FRI" aa:d0:43:06:46:e1 (on ch 6).
Twin = AL-GHUL ESP32-S3, reconfigured over serial.

Scenarios:
- A = twin + real AP, DIFFERENT BSSIDs (twin 02:a1..., real aa:d0...)
- B = twin CLONES the real BSSID aa:d0... (the hard case: one BSSID, two radios)
- C = single emitter only, control (the twin alone, real AP off; confirmed by IE + skew)

Captures: watcher-raw-{A,B,C}-2026110500*.jsonl  (carry tsf, NOT sn: pre-SN firmware)

## Headline table (DETECT / MISS / CLEAR / n.m.=not measured)

| Detector | A diff-BSSID | B exact-CLONE | C single (control) | Catches clone B? | FP on C? |
|---|---|---|---|---|---|
| rule-1 (BSSID count) | DETECT (2 bssid, 50%, ttd 0s) | MISS (1 bssid, 0%) | CLEAR (1 bssid) | NO | no |
| clock-skew (TSF fit RMSE) | DETECT (two skews -4 vs -31 ppm) | DETECT (RMSE 7.3e10 us) | CLEAR (RMSE 13 us) | YES | no |
| TSF-jump (monotonicity) | CLEAR | DETECT (32/164 jumps, 16 back) | CLEAR | YES | no |
| IE-fingerprint (non-ML) | radios differ (Jaccard 0.27) | DETECT (2 IE-sets/1 bssid) | CLEAR (1 IE-set) | YES | no |
| RSSI-bimodality | flag=artifact (73 dB sat.) | DETECT (39 dB, minor 0.17) | CLEAR (minor gate) | YES* | no* |
| multi-channel | flag (twin hops) | flag (aa:d0 1,2,6) | flag (twin hops) | yes-ish | YES |
| ensemble score (0..1) | 0.40 DETECT | 0.80 DETECT | 0.03 CLEAR | YES | no |
| beacon-rate | no flag (0.67x) | no flag (1.0x) | no flag (0.67x) | NO (blind) | no |
| inter-beacon timing | no flag (0/8) | no flag (0/47) | no flag (0/3) | NO (blind) | no |
| sequence-number | n.m. | n.m. | n.m. | code-ready, unmeasured | - |
| ML RandomForest | DETECT (expected) | DETECT (expected) | n.m. | expected, unmeasured | unknown |

\* RSSI-bimodality: real detection only in B (39 dB = two physical locations). Its A "flag"
is a saturation artifact (readings near -1 dB), and its C clear is only due to the minority-
fraction gate suppressing another artifact. Fragile; needs outlier trimming to be trusted.

## The decisive case: Scenario B (exact-BSSID clone)

rule-1 is BLIND (one BSSID = looks like one AP). The clone is caught by:
- clock-skew : single-line TSF fit explodes, RMSE 7.3e10 us vs 13-79 us genuine (~9 orders).
- TSF-jump   : 32/164 big jumps + 16 backward steps = two independent clocks. Cleanest.
- IE-fingerprint : 2 distinct beacon IE-sets under the one BSSID (real laptop's rich set incl.
  vendor OUI 00:e0:4c, plus the twin's sparse ESP32 set). Cheap, transparent, no ML.
- ensemble   : 0.80, well over threshold.

Blind on B (channel-hopping precondition unmet): beacon-rate, inter-beacon timing. These need
the sniffer LOCKED to ch 6 so it hears both beacon trains together; while hopping, the real AP
(ch 6) and the hopping twin are almost never co-channel with the sniffer at the same instant,
so only one train is heard per burst (beacon-rate stays ~1.0x, inter-beacon sub-fraction 0.0).

## False positives (Scenario C, a single emitter must read CLEAR)

Only multi-channel false-positives: a lone twin hops channels, so "this BSSID seen on several
channels" fires even with no clone present. It is a behavioural tell, not a clone detector.
Everything else is correctly CLEAR on C. The ensemble down-weights multi-channel (0.03) for
exactly this reason, and C scores 0.03 (CLEAR).

## One-line conclusion

No single cheap detector covers everything. rule-1 handles the easy different-BSSID twin and is
blind to the exact clone; the physical-layer detectors (clock-skew, TSF-jump) and the non-ML
IE-fingerprint are what catch the clone; RSSI/multi-channel each carry their own FP profile;
beacon-rate and inter-beacon are blind without a channel-locked capture. The ensemble, by
combining them, DETECTs A and B and stays CLEAR on C (0.40 / 0.80 / 0.03).

## On-board live result (not just offline)

The exact-clone detection is now demonstrated LIVE on the Watcher hardware, not only in
offline Python. The ESP32-S3 sniffer firmware runs rule-1 + IE-fingerprint + TSF-jump on
board and drives the LED. In a live Scenario B (twin cloning aa:d0 + real laptop hotspot on
aa:d0) the board logged DETECTED with reasons ["ie-mismatch","tsf-jump"] while live_bssids=1
(so rule-1 was blind), went CLEAR when the twin was alone, and recovered. Full serial
evidence: experiments/onboard-live-demo-2026-11-05.md.

## Provenance
rule-1 + clock-skew : watcher_compare.py -> watcher-summary-{A,B,C}-*.json
RSSI/multi-ch/TSF-jump/SN : detector_analysis.py (reads watcher-raw-*)
IE-fingerprint/beacon-rate/inter-beacon/ensemble : detector_analysis2.py (reads watcher-raw-*)
ML : watcher/ (RandomForest); see ml-watcher-limitations.md for why it is demoted.
Original raw logs are kept unmodified in this folder.
