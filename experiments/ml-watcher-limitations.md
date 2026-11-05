# ML "Watcher" (RandomForest arms-race) - limitations, measured facts

Facts and file/log evidence only. Reword in your own voice for the slide/report.
Purpose: demote the ML leg from a headline claim to a harness + a stated limitation,
and lean the project's detection result on the measured physical detectors instead.

## 1. The separation is hand-coded into the synthetic data
- watcher/src/synth.py fixes the real router's fingerprint and the twin's, with a
  built-in gap the classifier is guaranteed to find:
  - TWIN_JITTER_FLOOR = 3500 us vs REAL_JITTER = 2200 us (twin timing is forced noisier)
  - twin cap 0x0421 vs real cap 0x1431; reduced twin IE set; vendor IE optional
- Consequence: the RandomForest "discovers" exactly the differences the generator was
  told to create. 100% synthetic accuracy is circular, not evidence of detection skill.

## 2. The arms-race curve is flat in every log (the headline result is not shown)
- Real hardware (round-logs/armsrace-serial-20261001-222152.csv): 6 rounds,
  accuracy = 1.0000 on every round; deployed twin-detection dipped once (round 1,
  vendor_ie flip) then returned to 1.0. Genome barely moves.
- Synthetic (round-logs/armsrace-synth-*.csv): accuracy = 1.0000 for all 12 rounds.
- The intended H4 "evasion then recovery" zig-zag does not appear in any run.

## 3. Residual label leakage through laa_bit (and the hand-set tells)
- features.py excludes BSSID identity (good) but keeps laa_bit, derived from the BSSID
  first octet. In synth the twin's first octet is 02 (laa) vs real 3c, and in every
  real-hardware genome laa = true. So one feature is a near-perfect stand-in for the label.
- match_ie_set and vendor_ie are similarly hand-set tells rather than learned physics.
- Net: the model can reach 100% off a single correlated bit; no subtle fingerprint needed.

## 4. The train/test split does not test generalisation
- train.py uses train_test_split(stratify=y), NOT a grouped split, even though
  features.py returns `groups` (per-BSSID) precisely for that.
- Only two devices (one real, one twin); per-BSSID aggregate features (rssi_mean,
  interbeacon_mean/std) are identical across all rows of a BSSID.
- So every held-out row comes from a BSSID the model trained on -> the reported 100%
  is memorising two radios, not generalising to unseen devices.

## 5. Never validated against the real evil-twin captures
- In detector-comparison-results.md the ML column is literally "(expected)".
- It was never run on the real A/B/C captures, and its false-positive baseline against a
  twin-free network was never collected.

## What is actually solid (use this as the real result instead)
- The MEASURED physical-detector comparison (detector-comparison-results.md): clock-skew
  and TSF-jump catch the exact-BSSID clone (Scenario B) that rule-1 is blind to, on real
  captures, with honest per-detector failure modes; the IE-fingerprint detector recovers the
  clone case cheaply; the ensemble gives one clean score (A=0.40, B=0.80, C=0.03).

## Suggested framing (one line)
"We also built an AI-vs-AI arms-race harness (evolutionary attacker vs a RandomForest
Watcher). On our hardware the disguise search space was too coarse to produce real evasion,
so the detection curve stayed flat; we treat the arms race as a framework and a limitation,
and base our detection findings on the measured physical-layer detectors."
