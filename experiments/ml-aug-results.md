# Data-augmentation side experiment (2026-11-05)

Script: experiments/ml_aug.py. Window-level clone detector ("two emitters under one
identity?") with vs without physics-invariant augmentation. Features: log(clock-skew
fit RMSE), distinct IE-sets, RSSI spread, sequence-number discontinuity, beacon-rate,
inter-beacon sub-fraction. Augmentation = synthetic STEALTHY clones built by mixing the
two REAL sources and setting the twin's IE set equal to the real AP's (so the IE tell
n_ie collapses to 1). Real singles and real clones held out for testing.

## Result
| model | recall real clone | recall STEALTHY IE-matched clone | FPR on single AP |
|---|---|---|---|
| no augmentation | 1.00 | 0.10 | 0.00 |
| with augmentation | 1.00 | 1.00 | 0.00 |

train: singles=10, real-clones=238, synth-hard=60 ; test: singles=8, real-clones=159,
synth-hard(held-out)=60.

## Reading
Both catch the easy real clone. Against a stealthy twin that has cloned the IE set, the
plain model collapses to 10% (it had leaned on the IE tell); the augmented model, taught
the clock/sequence invariant, catches 100% at zero added false positives. This is the
evasion asymmetry in ML form: when the attacker evades the config tell, augmentation makes
the model fall back on the physics it cannot fake (clock-skew, sequence numbers).

## Honest limits
The stealthy clone is SYNTHETIC (physically motivated: a twin can clone IEs; we even tried
it, though the ESP32 vendor-IE broke the beacon). Small data; illustrative, not a benchmark.
The synthetic case is a training aid and an adversarial test, never a real measured result.
