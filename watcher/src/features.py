"""Turn raw sniffer records into the Watcher's feature table.

Design rule: we label frames by BSSID (real router vs anything else on the same
SSID), so we must NOT feed BSSID identity as a feature, that would be label
leakage. Instead we feed only radio/behavioural fingerprints that generalise:
beacon interval, beacon-timing jitter, RSSI distribution, the set of information
elements and their count, vendor-IE presence, capability bits, and the
locally-administered MAC bit (a real fingerprint the attacker can try to evade).
"""
from collections import defaultdict
import statistics as st
import pandas as pd

# A fixed vocabulary of common 802.11 IE tag ids -> stable one-hot columns.
COMMON_TAGS = [0, 1, 3, 5, 7, 32, 33, 35, 36, 42, 45, 46, 48, 50,
               61, 70, 74, 127, 191, 195, 221]


def laa_bit(bssid: str) -> int:
    """1 if the MAC is locally administered (bit 1 of the first octet)."""
    try:
        first = int(bssid.split(":")[0], 16)
        return (first >> 1) & 1
    except Exception:
        return 0


def _row_for(rec: dict, ib_mean, ib_std, rssi_mean, rssi_std) -> dict:
    ies = rec.get("ies", []) or []
    vendors = rec.get("vendors", []) or []
    row = {
        "beacon_interval": rec.get("bi", 0),
        "cap": rec.get("cap", 0),
        "rssi": rec.get("rssi", 0),
        "rssi_mean": rssi_mean,
        "rssi_std": rssi_std,
        "interbeacon_mean_us": ib_mean,
        "interbeacon_std_us": ib_std,
        "n_ies": len(ies),
        "n_vendors": len(vendors),
        "laa_bit": laa_bit(rec.get("bssid", "00")),
    }
    for tag in COMMON_TAGS:
        row[f"ie_{tag}"] = 1 if tag in ies else 0
    return row


def records_to_frame(records, real_bssid: str, target_ssid: str | None = None):
    """Return (X: DataFrame, y: list[int], groups: list[str]).

    y: 0 = real router, 1 = twin.  groups: the BSSID each row came from (useful
    for grouped train/test splits so the model cannot memorise a single device).
    """
    real_bssid = (real_bssid or "").lower()

    by_bssid = defaultdict(list)
    for r in records:
        if r.get("k") not in ("beacon", "probe_resp"):
            continue
        if target_ssid is not None and r.get("ssid") != target_ssid:
            continue
        if not r.get("bssid"):
            continue
        by_bssid[r["bssid"].lower()].append(r)

    rows, labels, groups = [], [], []
    for bssid, recs in by_bssid.items():
        recs.sort(key=lambda x: x.get("t", 0))
        ts = [x.get("t", 0) for x in recs]
        deltas = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
        rssis = [x.get("rssi", 0) for x in recs]
        ib_mean = st.mean(deltas) if deltas else 0.0
        ib_std = st.pstdev(deltas) if len(deltas) > 1 else 0.0
        rssi_mean = st.mean(rssis) if rssis else 0.0
        rssi_std = st.pstdev(rssis) if len(rssis) > 1 else 0.0
        label = 0 if bssid == real_bssid else 1
        for r in recs:
            rows.append(_row_for(r, ib_mean, ib_std, rssi_mean, rssi_std))
            labels.append(label)
            groups.append(bssid)

    X = pd.DataFrame(rows)
    if not X.empty:
        X = X.reindex(sorted(X.columns), axis=1)  # stable column order
    return X, labels, groups


def feature_columns() -> list[str]:
    base = ["beacon_interval", "cap", "rssi", "rssi_mean", "rssi_std",
            "interbeacon_mean_us", "interbeacon_std_us", "n_ies", "n_vendors",
            "laa_bit"]
    base += [f"ie_{t}" for t in COMMON_TAGS]
    return sorted(base)
