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

## Why the augmented number is 100% (and why to trust the DIRECTION, not the number)
The 100% is inflated, not a perfect detector:
1. The physical features are near-deterministic separators: a two-clock window has a
   single-line TSF fit error ~1e10 us vs a few us for one clock, and two interleaved
   sequence-number counters give a high discontinuity rate vs ~0 for one. Once the model
   uses them, separation is almost perfect by physics, not by cleverness.
2. In-distribution test: the synthetic stealthy clones used to TRAIN the augmented model
   and those used to TEST it share the same construction recipe (mix the two real sources,
   match the IE set). Source windows are disjoint, but the feature distribution is identical,
   so acing the test is partly guaranteed by construction.
3. Tiny test set (dozens of windows), so 100%/0% carries little statistical weight.
Report the DIRECTION (plain model misses the stealthy clone; augmentation makes it fall back
on the non-evadable clock/sequence signals), not the literal 100%.
