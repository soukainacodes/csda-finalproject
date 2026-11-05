#!/usr/bin/env python3
"""Side experiment: does data augmentation help the clone detector?

Task: window-level "two emitters under one identity?" (clone vs single).
Features (the ensemble signals): log(clock-skew fit RMSE), distinct IE-sets,
RSSI spread, sequence-number discontinuity, beacon-rate, inter-beacon sub-fraction.

The honest test of augmentation's worth: a STEALTHY twin that has cloned the real
AP's IE set (so n_ie = 1, the IE tell is gone). A model that leaned on the IE tell
should miss it; a model trained WITH physics-invariant augmentation (synthetic
IE-matched clones built by mixing the two real sources) should learn to fall back
on the clock / sequence signals and still catch it.

Augmentation is built from the TWO REAL sources (not fake devices); the real
singles and real clones are held out for testing; synthetic clones are only a
training aid and an adversarial test, never counted as a real result.
"""
import json, random
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import recall_score

HERE = Path(__file__).resolve().parent
random.seed(0); np.random.seed(0)

# single-emitter sources (capture -> bssids, each one emitter), with role
A_CAPS = ["watcher-onboard-raw-A-20261105-132518.jsonl",
          "watcher-onboard-raw-A-20261105-123817.jsonl",
          "watcher-onboard-raw-A-20261105-124953.jsonl"]
C_CAP = "watcher-onboard-raw-C-20261105-125911.jsonl"            # twin alone (aa:d0)
CLONE_CAPS = ["watcher-onboard-raw-B-20261105-132355.jsonl",
              "watcher-onboard-raw-B-20261105-125100.jsonl",
              "watcher-onboard-raw-ChLock6-20261105-140320.jsonl"]
REAL_BSSID = "aa:d0:43:06:46:e1"; TWIN_BSSID = "02:a1:00:00:00:01"
TU = 1024


def beacons(path):
    out = []
    for ln in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                o = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if o.get("ssid") == "Kaffi_FRI" and o.get("k") == "beacon":
                out.append(o)
    return out


def feats(window):
    w = sorted(window, key=lambda o: o.get("t", 0))
    ts = [o.get("t", 0) for o in w]; tsfs = [o.get("tsf", 0) for o in w]
    rssis = [o.get("rssi", 0) for o in w]; sns = [o.get("sn") for o in w]
    ies = set(tuple(o.get("ies", []) or []) for o in w)
    n = len(w)
    mx = sum(ts) / n; my = sum(tsfs) / n
    sxx = sum((x - mx) ** 2 for x in ts)
    if sxx:
        sl = sum((ts[i] - mx) * (tsfs[i] - my) for i in range(n)) / sxx; b = my - sl * mx
        rmse = (sum((tsfs[i] - (sl * ts[i] + b)) ** 2 for i in range(n)) / n) ** 0.5
    else:
        rmse = 0.0
    sv = [s for s in sns if s is not None]
    snf = (sum(1 for k in range(1, len(sv)) if (sv[k] - sv[k - 1]) % 4096 > 2048) / (len(sv) - 1)) if len(sv) >= 4 else 0.0
    dur = (ts[-1] - ts[0]) / 1e6 if n > 1 else 0
    rate = (n - 1) / dur if dur > 0 else 0
    gaps = [ts[k] - ts[k - 1] for k in range(1, n)]
    inb = [g for g in gaps if g <= 300000]
    sub = (sum(1 for g in inb if g < 0.7 * 100 * TU) / len(inb)) if inb else 0.0
    return [np.log10(rmse + 1), len(ies), max(rssis) - min(rssis), snf, rate, sub]


def slide(lst, size=20, stride=6, lo=12):
    return [lst[i:i + size] for i in range(0, max(1, len(lst) - size + 1), stride) if len(lst[i:i + size]) >= lo]


# gather windows
real_single, twin_single, clone_real = [], [], []
for cap in A_CAPS:
    by = {}
    for o in beacons(HERE / cap):
        by.setdefault(o["bssid"], []).append(o)
    real_single += slide(sorted(by.get(REAL_BSSID, []), key=lambda x: x.get("t", 0)))
    twin_single += slide(sorted(by.get(TWIN_BSSID, []), key=lambda x: x.get("t", 0)))
twin_single += slide(sorted([o for o in beacons(HERE / C_CAP) if o["bssid"] == REAL_BSSID], key=lambda x: x.get("t", 0)))
for cap in CLONE_CAPS:
    lst = sorted([o for o in beacons(HERE / cap) if o["bssid"] == REAL_BSSID], key=lambda x: x.get("t", 0))
    clone_real += slide(lst)

single = real_single + twin_single


def split(xs, frac=0.6):
    k = int(len(xs) * frac); return xs[:k], xs[k:]


rs_tr, rs_te = split(real_single); tw_tr, tw_te = split(twin_single)
sn_tr = rs_tr + tw_tr; sn_te = rs_te + tw_te
cl_tr, cl_te = split(clone_real)


def synth_hard(real_ws, twin_ws, k=40):
    """Stealthy IE-matched clones: mix a real-AP window + a twin window, and set the
    twin beacons' IE set equal to the real AP's (so the IE tell n_ie collapses to 1)."""
    out = []
    for _ in range(k):
        if not real_ws or not twin_ws:
            break
        r = random.choice(real_ws); t = random.choice(twin_ws)
        rie = r[0].get("ies", [])
        tw = [dict(o) for o in t]
        for o in tw:
            o["ies"] = rie                       # twin clones the IE set
        out.append(r[:12] + tw[:12])
    return out


hard_tr = synth_hard(rs_tr, tw_tr, 60)   # for augmented training
hard_te = synth_hard(rs_te, tw_te, 60)   # adversarial test (held-out sources)

# feature matrices
Xsn_tr = [feats(w) for w in sn_tr]; Xcl_tr = [feats(w) for w in cl_tr]
Xsn_te = [feats(w) for w in sn_te]; Xcl_te = [feats(w) for w in cl_te]
Xhard_tr = [feats(w) for w in hard_tr]; Xhard_te = [feats(w) for w in hard_te]

rf = lambda: RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1)

# model WITHOUT augmentation: real singles + real clones
Xa = Xsn_tr + Xcl_tr; ya = [0] * len(Xsn_tr) + [1] * len(Xcl_tr)
m_no = rf().fit(Xa, ya)
# model WITH augmentation: + synthetic IE-matched (stealthy) clones
Xb = Xa + Xhard_tr; yb = ya + [1] * len(Xhard_tr)
m_aug = rf().fit(Xb, yb)


def rep(name, m):
    r_easy = recall_score([1] * len(Xcl_te), m.predict(Xcl_te), zero_division=0) if Xcl_te else 0
    r_hard = recall_score([1] * len(Xhard_te), m.predict(Xhard_te), zero_division=0) if Xhard_te else 0
    fp = sum(m.predict(Xsn_te)) / len(Xsn_te) if Xsn_te else 0   # false-positive rate on singles
    print(f"  {name:16s} recall(real clone)={r_easy:.2f}  recall(STEALTHY IE-matched clone)={r_hard:.2f}  FPR(single)={fp:.2f}")


print("=" * 72)
print("CLONE DETECTOR, with vs without physics-invariant augmentation")
print(f"  train singles={len(sn_tr)} real-clones={len(cl_tr)} synth-hard={len(hard_tr)}")
print(f"  test  singles={len(sn_te)} real-clones={len(cl_te)} synth-hard(held-out)={len(hard_te)}")
rep("no augmentation", m_no)
rep("augmentation", m_aug)
print("=" * 72)
print("Reading: both catch the easy real clone. The stealthy IE-matched clone is the")
print("test of worth, does augmentation lift recall on it without raising false positives?")
