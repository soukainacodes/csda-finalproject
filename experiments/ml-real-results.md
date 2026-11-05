# RandomForest trained on the REAL Watcher captures (2026-11-05)

Honest retrain of the ML on real data (replacing the discredited synthetic model).
Script: experiments/ml_real.py. No synthetic data. Labels from the known experiment
setup, never the BSSID. BSSID / source-MAC / SSID / locally-administered bit excluded
as features.

## Primary: temporal split on real captures (A two-BSSID + C twin-alone)
- train 106 beacons, test 72 (21 twin / 51 real), temporal 60/40 split per capture.
- accuracy 1.000, precision 1.000, recall 1.000, FALSE-POSITIVE RATE 0.000.
- confusion: tn 51, fp 0, fn 0, tp 21.
- HONEST SCOPE: two physical radios only (one laptop AP, one ESP32 twin). 100% here is
  SEPARABILITY of these two radios, NOT generalization to unseen hardware.

## Feature importances (the real result: does the ML pick the physics?)
  has70        0.163   (IE fingerprint: real AP carries tag 70)
  w_skew_ppm   0.163   (clock skew, the physical oscillator fingerprint)
  n_vendors    0.161   (IE fingerprint)
  w_ibi_mean   0.155   (inter-beacon timing)
  n_ies        0.134   (IE fingerprint)
  n221         0.125   (IE fingerprint)
  w_ibi_std    0.055 ; w_rssi_mean 0.021 ; rssi 0.014 ; w_rssi_std 0.008 ;
  w_skew_rmse 0.001 ; w_sn_frac 0.000 ; cap 0.000 ; bi 0.000
- The model INDEPENDENTLY ranks clock-skew + IE fingerprint + inter-beacon timing top,
  the same tells the hand detectors use. w_skew_rmse and w_sn_frac are ~0 here because in
  A/C each emitter is a single clock (rmse/sn discriminate the CLONE at window level, not
  twin-vs-real per beacon).

## Cross-scenario: train on real A+C, predict the exact clone B (IE ground-truth)
- B: 69 beacons (15 twin / 54 real by IE-signature).
- full-feature model accuracy on B = 1.000 (uses IE; B ground-truth is IE-based, so this
  is expected rather than independent).
- clock/timing-only model (no IE/cap) accuracy on B = 0.783. This is the independent check:
  using only clock + timing, a model trained on the two-BSSID case still classifies 78% of
  the unseen exact-clone beacons.

## Honest bottom line
A properly-trained RandomForest on real data separates twin from real perfectly with zero
false positives (two-device separability, not generalization) and independently confirms the
physical tells (clock-skew, IE fingerprint, timing). The clock/timing signals transfer 78% to
the unseen clone. Reported as corroboration + separability, with the two-device scope stated.
Figure: plots/fig_ml.png.
