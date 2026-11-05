#!/usr/bin/env python3
"""Offline detectors run on already-captured Watcher data (no new hardware).

Adds three more evil-twin detectors beside rule-1 and clock-skew, each computed
per BSSID of the target SSID from the raw beacon logs:

  RSSI-BIMODALITY : two APs at two locations => a single (cloned) BSSID shows two
                    RSSI clusters (1-D k-means, flag if well-separated).
  MULTI-CHANNEL   : one legit AP lives on one channel; a BSSID seen on several
                    channels is a hopping/cloned radio.
  TSF-JUMP        : under one BSSID the TSF must rise smoothly with local time;
                    backward or huge jumps mean two independent clocks (a clone).

Reads watcher-raw-{A,B,C}-*.jsonl in this folder and prints a comparison.
"""
from __future__ import annotations
import json, glob, statistics
from pathlib import Path

TARGET = "Kaffi_FRI"
HERE = Path(__file__).resolve().parent


def kmeans2(vals):
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
            lo, hi = nlo, nhi
            break
        lo, hi = nlo, nhi
    sep = abs(hi - lo)
    minor = min(len(a), len(b)) / len(vals)
    return {"sep_db": round(sep, 1), "minor_frac": round(minor, 2),
            "bimodal": sep >= 10 and minor >= 0.15}


def analyse(path: Path):
    per = {}   # bssid -> {"rssi":[], "ch":set(), "ts":[(t,tsf)]}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("k") not in ("beacon", "probe_resp") or o.get("ssid") != TARGET:
            continue
        b = o.get("bssid")
        d = per.setdefault(b, {"rssi": [], "ch": set(), "ts": [], "sn": []})
        if o.get("rssi") is not None:
            d["rssi"].append(o["rssi"])
        if o.get("ch") is not None:
            d["ch"].add(o["ch"])
        if o.get("t") is not None and o.get("tsf") is not None:
            d["ts"].append((o["t"], o["tsf"]))
        if o.get("t") is not None and o.get("sn") is not None:
            d["sn"].append((o["t"], o["sn"]))

    out = {}
    for b, d in per.items():
        # RSSI bimodality
        bim = kmeans2(d["rssi"]) if len(d["rssi"]) >= 10 else None
        # multi-channel
        multi = {"n_channels": len(d["ch"]), "channels": sorted(d["ch"]),
                 "flag": len(d["ch"]) > 1}
        # TSF jumps: order by local time, count pairs where tsf step is far from the time step
        ts = sorted(d["ts"])
        jumps = back = 0
        for i in range(1, len(ts)):
            dt = ts[i][0] - ts[i - 1][0]
            dtsf = ts[i][1] - ts[i - 1][1]
            if dtsf < 0:
                back += 1
            if dt > 0 and abs(dtsf - dt) > 100_000:   # off by > 0.1 s from local clock
                jumps += 1
        pairs = max(1, len(ts) - 1)
        tsfj = {"pairs": pairs, "backward": back, "big_jumps": jumps,
                "jump_frac": round(jumps / pairs, 2), "flag": (jumps / pairs) > 0.1 or back > 0}
        # sequence-number discontinuity (present only on SN-carrying captures)
        snd = None
        if d["sn"]:
            sns = sorted(d["sn"])
            bigstep = 0
            for i in range(1, len(sns)):
                step = (sns[i][1] - sns[i - 1][1]) % 4096   # forward distance mod wrap
                if step > 2048:                              # looks like a backward jump = 2nd counter
                    bigstep += 1
            sp = max(1, len(sns) - 1)
            snd = {"pairs": sp, "backward_like": bigstep, "frac": round(bigstep / sp, 2),
                   "flag": (bigstep / sp) > 0.2}
        out[b] = {"n": len(d["rssi"]), "rssi_bimodality": bim,
                  "multi_channel": multi, "tsf_jump": tsfj, "seq_num": snd}
    return out


def main():
    for scen in ("A", "B", "C"):
        files = sorted(glob.glob(str(HERE / f"watcher-raw-{scen}-*.jsonl")))
        if not files:
            continue
        path = Path(files[-1])
        print("=" * 72)
        print(f"SCENARIO {scen}   ({path.name})")
        res = analyse(path)
        for b, r in res.items():
            bim = r["rssi_bimodality"]
            bim_s = (f"bimodal={bim['bimodal']} sep={bim['sep_db']}dB minor={bim['minor_frac']}"
                     if bim else "n/a")
            mc = r["multi_channel"]
            tj = r["tsf_jump"]
            print(f"  {b}  n={r['n']}")
            print(f"     RSSI-bimodality : {bim_s}")
            print(f"     multi-channel   : flag={mc['flag']} channels={mc['channels']}")
            print(f"     TSF-jump        : flag={tj['flag']} big_jumps={tj['big_jumps']}/{tj['pairs']} backward={tj['backward']}")
            sn = r["seq_num"]
            sn_s = (f"flag={sn['flag']} backward-like={sn['backward_like']}/{sn['pairs']} frac={sn['frac']}"
                    if sn else "no sn in this capture (pre-SN firmware)")
            print(f"     seq-number      : {sn_s}")
        # scenario verdict per detector (any BSSID flagged)
        v_bim = any(r["rssi_bimodality"] and r["rssi_bimodality"]["bimodal"] for r in res.values())
        v_mc  = any(r["multi_channel"]["flag"] for r in res.values())
        v_tj  = any(r["tsf_jump"]["flag"] for r in res.values())
        v_sn  = any(r["seq_num"] and r["seq_num"]["flag"] for r in res.values())
        print(f"  VERDICT  rssi-bimodal={v_bim}  multi-channel={v_mc}  tsf-jump={v_tj}  seq-num={v_sn}")
    print("=" * 72)


if __name__ == "__main__":
    main()
