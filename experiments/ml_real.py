#!/usr/bin/env python3
"""A properly-trained RandomForest on the REAL Watcher captures (no synthetic data).

Honest by construction:
  - labels come from the known experiment setup, NEVER from the BSSID;
  - BSSID, source MAC, SSID and the locally-administered bit are excluded as features
    (those were the old model's leaks);
  - features are the physical / structural signals the hand detectors use;
  - split is temporal within each capture (no shuffling across time);
  - we report accuracy, precision, recall, FALSE-POSITIVE RATE, confusion and the
    FEATURE IMPORTANCES (the real question: does the model pick the physical tells?);
  - a cross-scenario test trains on A+C and predicts the exact clone (B), with and
    without the IE features, to see which signals carry it.

Honest scope: one real AP + one twin, so this measures signal separability and fusion,
NOT generalization to unseen hardware. Stated, not hidden.
"""
import json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score

HERE = Path(__file__).resolve().parent
W = 12  # sliding window (beacons) for the per-radio aggregates

# capture -> {bssid: label}   label 1 = twin, 0 = real (from the known setup)
CAPS = {
    "watcher-onboard-raw-A-20261105-132518.jsonl": {"02:a1:00:00:00:01": 1, "aa:d0:43:06:46:e1": 0},
    "watcher-onboard-raw-A-20261105-123817.jsonl": {"02:a1:00:00:00:01": 1, "aa:d0:43:06:46:e1": 0},
    "watcher-onboard-raw-A-20261105-124953.jsonl": {"02:a1:00:00:00:01": 1, "aa:d0:43:06:46:e1": 0},
    "watcher-onboard-raw-C-20261105-125911.jsonl": {"aa:d0:43:06:46:e1": 1},   # twin alone (cloned id)
}
B_CAP = "watcher-onboard-raw-B-20261105-132355.jsonl"   # exact clone, held out

FEATS = ["bi", "cap", "rssi", "n_ies", "n_vendors", "has70", "n221",
         "w_rssi_mean", "w_rssi_std", "w_ibi_mean", "w_ibi_std",
         "w_skew_ppm", "w_skew_rmse", "w_sn_frac"]
NOIE = ["bi", "rssi", "w_rssi_mean", "w_rssi_std", "w_ibi_mean", "w_ibi_std",
        "w_skew_ppm", "w_skew_rmse", "w_sn_frac"]   # clock/timing only


def beacons(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("ssid") == "Kaffi_FRI" and o.get("k") == "beacon":
            out.append(o)
    return out


def skew(ts, tsfs):
    n = len(ts)
    if n < 3:
        return 0.0, 0.0
    mx = sum(ts) / n; my = sum(tsfs) / n
    sxx = sum((x - mx) ** 2 for x in ts)
    if sxx == 0:
        return 0.0, 0.0
    slope = sum((ts[i] - mx) * (tsfs[i] - my) for i in range(n)) / sxx
    b = my - slope * mx
    rmse = (sum((tsfs[i] - (slope * ts[i] + b)) ** 2 for i in range(n)) / n) ** 0.5
    return (slope - 1.0) * 1e6, rmse


def rows_for(path, labelmap=None, cap_tag=""):
    """labelmap None => cross-test rows with IE ground-truth in column 'label'."""
    by = {}
    for o in beacons(path):
        by.setdefault(o["bssid"], []).append(o)
    out = []
    for bssid, lst in by.items():
        if labelmap is not None and bssid not in labelmap:
            continue
        lst.sort(key=lambda x: x.get("t", 0))
        for i in range(len(lst)):
            w = lst[max(0, i - W + 1):i + 1]
            if len(w) < 4:
                continue
            o = lst[i]; ies = o.get("ies", []) or []
            ts = [x.get("t", 0) for x in w]; tsfs = [x.get("tsf", 0) for x in w]
            rssis = [x.get("rssi", 0) for x in w]; sns = [x.get("sn") for x in w]
            ibi = [ts[k] - ts[k - 1] for k in range(1, len(ts))]
            sk, rm = skew(ts, tsfs)
            sv = [s for s in sns if s is not None]; snf = 0.0
            if len(sv) >= 4:
                big = sum(1 for k in range(1, len(sv)) if (sv[k] - sv[k - 1]) % 4096 > 2048)
                snf = big / (len(sv) - 1)
            if labelmap is not None:
                lab = labelmap[bssid]
            else:
                lab = 0 if (70 in ies or len(ies) >= 12) else 1   # IE ground-truth for B
            out.append({
                "bi": o.get("bi", 0), "cap": o.get("cap", 0), "rssi": o.get("rssi", 0),
                "n_ies": len(ies), "n_vendors": len(o.get("vendors", []) or []),
                "has70": 1 if 70 in ies else 0, "n221": sum(1 for t in ies if t == 221),
                "w_rssi_mean": float(np.mean(rssis)), "w_rssi_std": float(np.std(rssis)),
                "w_ibi_mean": float(np.mean(ibi)) if ibi else 0.0,
                "w_ibi_std": float(np.std(ibi)) if ibi else 0.0,
                "w_skew_ppm": sk, "w_skew_rmse": rm, "w_sn_frac": snf,
                "label": lab, "cap_tag": cap_tag, "t": o.get("t", 0),
            })
    return out


# ---- build real labelled table ----
rows = []
for p, lm in CAPS.items():
    rows += rows_for(HERE / p, lm, p[:-6])   # tag by full capture name so the 3 A sessions split independently
df = pd.DataFrame(rows)

# ---- temporal split per capture (first 60% train, last 40% test) ----
tr, te = [], []
for _, g in df.groupby("cap_tag"):
    g = g.sort_values("t"); k = int(len(g) * 0.6)
    tr += list(g.index[:k]); te += list(g.index[k:])
clf = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1)
clf.fit(df.loc[tr, FEATS], df.loc[tr, "label"])
yte = df.loc[te, "label"]; pred = clf.predict(df.loc[te, FEATS])
tn, fp, fn, tp = confusion_matrix(yte, pred, labels=[0, 1]).ravel()
fpr = fp / (fp + tn) if (fp + tn) else 0.0

print("=" * 66)
print("PRIMARY  temporal split on REAL captures (A two-BSSID + C twin-alone)")
print(f"  train={len(tr)}  test={len(te)}  test twin={int(sum(yte))}/{len(yte)}")
print(f"  accuracy ={accuracy_score(yte, pred):.3f}")
print(f"  precision={precision_score(yte, pred, zero_division=0):.3f}  recall={recall_score(yte, pred, zero_division=0):.3f}")
print(f"  FALSE-POSITIVE RATE (real flagged as twin) = {fpr:.3f}   confusion tn={tn} fp={fp} fn={fn} tp={tp}")
print("  feature importances (does it pick the physical tells?):")
for f, v in sorted(zip(FEATS, clf.feature_importances_), key=lambda x: -x[1]):
    print(f"     {f:13s} {v:5.3f}")

# ---- cross-scenario: train on all real A+C, test on the exact clone B ----
bdf = pd.DataFrame(rows_for(HERE / B_CAP, None, "B"))
full = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1).fit(df[FEATS], df["label"])
noie = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1).fit(df[NOIE], df["label"])
acc_f = accuracy_score(bdf["label"], full.predict(bdf[FEATS]))
acc_n = accuracy_score(bdf["label"], noie.predict(bdf[NOIE]))
print("=" * 66)
print("CROSS-SCENARIO  train on real A+C, predict the exact clone B (IE ground-truth)")
print(f"  B beacons={len(bdf)}  twin={int(sum(bdf['label']))}  real={len(bdf)-int(sum(bdf['label']))}")
print(f"  clock/timing-only model accuracy on B = {acc_n:.3f}   <- HEADLINE: no IE, independent of the IE-based labels")
print(f"  full-feature model accuracy on B      = {acc_f:.3f}   (sanity check only: uses IE, and B's labels are IE-derived, so partly tautological)")
print("=" * 66)

# ---- save a feature-importance figure ----
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    imp = sorted(zip(FEATS, clf.feature_importances_), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    ax.barh([f for f, _ in imp], [v for _, v in imp], color="#23237a")
    ax.set_xlabel("RandomForest feature importance", fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    plt.rcParams["font.family"] = "serif"
    fig.tight_layout(); fig.savefig(HERE / "plots" / "fig_ml.png", dpi=150, facecolor="white")
    print("wrote plots/fig_ml.png")
except Exception as e:
    print("(figure skipped:", e, ")")
