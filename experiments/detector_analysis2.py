#!/usr/bin/env python3
"""Four more evil-twin detectors, run offline on the SAME raw Watcher captures.

No new hardware, no new capture: these read watcher-raw-{A,B,C}-*.jsonl exactly as
detector_analysis.py does. They are the "refinement" detectors:

  IE-FINGERPRINT   : (a) intra-BSSID multiplicity, how many distinct beacon IE-sets
                     appear under ONE BSSID (a single AP emits one stable set, so >1
                     means two emitters sharing a BSSID = a clone). (b) cross-BSSID
                     Jaccard distance of the IE sets when the SSID is on >1 BSSID.
                     This is "the ML's input, without the ML".
  BEACON-RATE      : within a reception burst (gaps < 300 ms, i.e. one channel dwell),
                     beacons/second per BSSID. One AP at bi=100 TU ~= 9.8/s; two
                     emitters under one BSSID roughly double it.
  INTERBEACON      : the spacing between consecutive beacon arrivals (local time, NOT
                     the TSF). One AP => gaps cluster at the beacon interval and its
                     multiples; two interleaved trains add a cluster well below one
                     interval. We flag the fraction of in-burst gaps below 0.7*bi.
  ENSEMBLE         : combine the per-BSSID signals (clock-skew RMSE, TSF jumps, IE
                     multiplicity, RSSI bimodality, interbeacon sub-interval, plus the
                     SSID-level second-BSSID rule) into one 0..1 anomaly score.

Lab use only, passive, receive-only. Reads and writes this folder.
"""
from __future__ import annotations
import json, glob, statistics as st
from pathlib import Path

TARGET = "Kaffi_FRI"
HERE = Path(__file__).resolve().parent
BURST_GAP_US = 300_000          # gaps under this = same channel-dwell burst
TU_US = 1024                    # one 802.11 Time Unit in microseconds


def linfit(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n; my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    slope = sxy / sxx; b = my - slope * mx
    rmse = (sum((ys[i] - (slope * xs[i] + b)) ** 2 for i in range(n)) / n) ** 0.5
    return slope, b, rmse


def kmeans2(vals):
    """1-D two-means; returns separation + minority fraction, or None."""
    vals = [v for v in vals if -90 <= v <= -5]      # trim saturated/invalid RSSI
    if len(vals) < 10:
        return None
    s = sorted(vals)
    lo, hi = s[len(s) // 4], s[3 * len(s) // 4]
    a, b = [], []
    for _ in range(25):
        a = [v for v in vals if abs(v - lo) <= abs(v - hi)]
        b = [v for v in vals if abs(v - lo) > abs(v - hi)]
        if not a or not b:
            return {"sep_db": 0.0, "minor_frac": 0.0, "bimodal": False}
        nlo, nhi = sum(a) / len(a), sum(b) / len(b)
        if abs(nlo - lo) < 0.05 and abs(nhi - hi) < 0.05:
            lo, hi = nlo, nhi; break
        lo, hi = nlo, nhi
    sep = abs(hi - lo); minor = min(len(a), len(b)) / len(vals)
    return {"sep_db": round(sep, 1), "minor_frac": round(minor, 2),
            "bimodal": sep >= 10 and minor >= 0.15}


def ie_key(o):
    """A stable fingerprint of one frame's advertised capabilities."""
    return (tuple(o.get("ies", []) or []), o.get("cap"), o.get("bi"),
            tuple(o.get("vendors", []) or []))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / len(a | b)


def load(path: Path):
    per = {}   # bssid -> dict of lists
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("ssid") != TARGET or o.get("k") not in ("beacon", "probe_resp"):
            continue
        b = o.get("bssid")
        d = per.setdefault(b, {"beacon_ie": set(), "ie_all": set(), "ch": set(),
                               "rssi": [], "ts": [], "beacon_ts": [], "bi": None})
        d["ie_all"].add(ie_key(o))
        if o.get("k") == "beacon":
            d["beacon_ie"].add(tuple(o.get("ies", []) or []))
            if o.get("t") is not None:
                d["beacon_ts"].append(o["t"])
            if d["bi"] is None and o.get("bi"):
                d["bi"] = o["bi"]
        if o.get("ch") is not None:
            d["ch"].add(o["ch"])
        if o.get("rssi") is not None:
            d["rssi"].append(o["rssi"])
        if o.get("t") is not None and o.get("tsf") is not None:
            d["ts"].append((o["t"], o["tsf"]))
    return per


def bursts(ts_sorted):
    """Split a sorted time list into bursts separated by > BURST_GAP_US."""
    out, cur = [], []
    for t in ts_sorted:
        if cur and t - cur[-1] > BURST_GAP_US:
            out.append(cur); cur = []
        cur.append(t)
    if cur:
        out.append(cur)
    return out


def analyse(path: Path):
    per = load(path)
    # union IE set per BSSID for the cross-BSSID comparison
    union_ie = {b: set().union(*d["beacon_ie"]) if d["beacon_ie"] else set()
                for b, d in per.items()}
    res = {}
    for b, d in per.items():
        # --- IE fingerprint ---
        intra = len(d["beacon_ie"])                 # distinct beacon IE-sets under this BSSID
        others = [ob for ob in per if ob != b]
        xdist = (round(min(jaccard(union_ie[b], union_ie[ob]) for ob in others), 2)
                 if others else None)
        ie = {"intra_distinct": intra, "cross_bssid_jaccard": xdist,
              "flag": intra > 1}

        # --- beacon-rate (within-burst) ---
        bts = sorted(d["beacon_ts"])
        bi = d["bi"] or 100
        nominal = 1e6 / (bi * TU_US)                # beacons/s a single AP would emit
        rates = []
        for burst in bursts(bts):
            if len(burst) >= 3:
                span = (burst[-1] - burst[0]) / 1e6
                if span > 0:
                    rates.append((len(burst) - 1) / span)
        burst_rate = round(st.median(rates), 1) if rates else None
        rate_ratio = round(burst_rate / nominal, 2) if burst_rate else None
        brate = {"burst_rate_hz": burst_rate, "nominal_hz": round(nominal, 1),
                 "ratio": rate_ratio, "flag": bool(rate_ratio and rate_ratio >= 1.6)}

        # --- inter-beacon arrival timing ---
        gaps = [bts[i] - bts[i - 1] for i in range(1, len(bts))]
        in_burst = [g for g in gaps if g <= BURST_GAP_US]
        thresh = 0.7 * bi * TU_US
        short = sum(1 for g in in_burst if g < thresh)
        sub_frac = round(short / len(in_burst), 2) if in_burst else 0.0
        inter = {"in_burst_gaps": len(in_burst), "subinterval": short,
                 "sub_frac": sub_frac, "flag": sub_frac > 0.2 and len(in_burst) >= 8}

        # --- reused physical signals for the ensemble ---
        ts = sorted(d["ts"])
        fit = linfit([p[0] for p in ts], [p[1] for p in ts]) if len(ts) >= 3 else None
        rmse = fit[2] if fit else None
        back = sum(1 for i in range(1, len(ts)) if ts[i][1] - ts[i - 1][1] < 0)
        bim = kmeans2(d["rssi"])
        multi_ch = len(d["ch"]) > 1

        signals = {
            "second_emitter_ie": ie["flag"],
            "clock_skew_rmse_hi": bool(rmse and rmse > 1e3),
            "tsf_backward": back > 0,
            "beacon_rate_hi": brate["flag"],
            "interbeacon_sub": inter["flag"],
            "rssi_bimodal": bool(bim and bim["bimodal"]),
            "multi_channel": multi_ch,
        }
        # weights: physical/structural tells trust > behavioural (multi_channel is weak,
        # a lone twin hops channels while hunting an uplink, so it must not dominate).
        W = {"second_emitter_ie": 0.30, "clock_skew_rmse_hi": 0.25, "tsf_backward": 0.15,
             "beacon_rate_hi": 0.10, "interbeacon_sub": 0.10, "rssi_bimodal": 0.07,
             "multi_channel": 0.03}
        score = round(sum(W[k] for k, v in signals.items() if v), 2)

        res[b] = {"n_beacon": len(bts), "ie": ie, "beacon_rate": brate,
                  "interbeacon": inter, "clock_rmse_us": round(rmse, 1) if rmse else None,
                  "tsf_backward": back, "rssi_bimodal": bool(bim and bim["bimodal"]),
                  "signals": signals, "anomaly_score": score}
    return res


def main():
    for scen in ("A", "B", "C"):
        files = sorted(glob.glob(str(HERE / f"watcher-raw-{scen}-*.jsonl")))
        if not files:
            continue
        path = Path(files[-1])
        print("=" * 74)
        print(f"SCENARIO {scen}   ({path.name})")
        res = analyse(path)
        n_bssid = len(res)
        for b, r in res.items():
            ie = r["ie"]; br = r["beacon_rate"]; it = r["interbeacon"]
            print(f"  {b}  beacons={r['n_beacon']}")
            print(f"     IE-fingerprint : intra_distinct={ie['intra_distinct']} "
                  f"cross_jaccard={ie['cross_bssid_jaccard']} flag={ie['flag']}")
            print(f"     beacon-rate    : burst={br['burst_rate_hz']}Hz "
                  f"nominal={br['nominal_hz']}Hz ratio={br['ratio']} flag={br['flag']}")
            print(f"     interbeacon    : sub_frac={it['sub_frac']} "
                  f"({it['subinterval']}/{it['in_burst_gaps']}) flag={it['flag']}")
            print(f"     anomaly_score  : {r['anomaly_score']}   signals="
                  f"{[k for k,v in r['signals'].items() if v]}")
        # SSID-level second-BSSID (rule-1) folds into the ensemble verdict
        second_bssid = n_bssid >= 2
        v_ie   = any(r["ie"]["flag"] for r in res.values())
        v_rate = any(r["beacon_rate"]["flag"] for r in res.values())
        v_int  = any(r["interbeacon"]["flag"] for r in res.values())
        best_score = max((r["anomaly_score"] for r in res.values()), default=0.0)
        ens_score = round(min(1.0, best_score + (0.30 if second_bssid else 0.0)), 2)
        print(f"  SSID second-BSSID (rule-1): {second_bssid}")
        print(f"  VERDICT  ie-fingerprint={v_ie}  beacon-rate={v_rate}  "
              f"interbeacon={v_int}  ENSEMBLE_score={ens_score} -> "
              f"{'DETECT' if ens_score >= 0.30 else 'CLEAR'}")
    print("=" * 74)


if __name__ == "__main__":
    main()
