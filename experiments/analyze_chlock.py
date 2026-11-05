#!/usr/bin/env python3
"""Run the channel-dependent detectors on a channel-LOCKED capture.

Sequence-number, beacon-rate and inter-beacon timing were blind on the hopping
captures because the two emitters were rarely on the sniffer's channel together.
With the Watcher locked to ch6 (the real AP's channel), both the real AP and the
twin's ch6 visits are captured co-channel, so these detectors can finally be
measured. Pass the channel-locked raw file:

    python analyze_chlock.py watcher-onboard-raw-ChLock6-YYYYMMDD-HHMMSS.jsonl
"""
import json, sys, statistics as st
from pathlib import Path

TARGET = "Kaffi_FRI"
TU_US = 1024


def main():
    path = Path(sys.argv[1])
    per = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("ssid") != TARGET or o.get("k") != "beacon":
            continue
        b = o.get("bssid")
        d = per.setdefault(b, {"t": [], "sn": [], "tsf": [], "rssi": [], "ies": set(),
                               "bi": o.get("bi", 100), "ch": set()})
        if o.get("t") is not None:
            d["t"].append(o["t"])
            d["sn"].append(o.get("sn"))
            d["tsf"].append(o.get("tsf"))
            d["rssi"].append(o.get("rssi"))
        d["ies"].add(tuple(o.get("ies", [])))
        if o.get("ch") is not None:
            d["ch"].add(o["ch"])

    print("=" * 70)
    print(f"channel-locked analysis  ({path.name})")
    for b, d in per.items():
        n = len(d["t"])
        order = sorted(range(n), key=lambda i: d["t"][i])
        t = [d["t"][i] for i in order]
        sn = [d["sn"][i] for i in order]
        bi = d["bi"] or 100
        dur = (t[-1] - t[0]) / 1e6 if n > 1 else 0

        # --- sequence-number discontinuity ---
        sn_ok = [x for x in sn if x is not None]
        snd = "no sn field"
        if len(sn_ok) == len(sn) and n > 2:
            big = back = 0
            for i in range(1, n):
                if sn[i] is None or sn[i-1] is None:
                    continue
                step = (sn[i] - sn[i-1]) % 4096
                if step > 2048:
                    big += 1
                if sn[i] < sn[i-1]:
                    back += 1
            pairs = max(1, n-1)
            snd = f"big_backsteps={big}/{pairs} frac={big/pairs:.2f} flag={big/pairs>0.2}"

        # --- beacon-rate (overall + peak 5 s window) ---
        nominal = 1e6 / (bi * TU_US)
        overall = (n-1)/dur if dur > 0 else 0
        peak = 0
        if n > 2:
            j = 0
            for i in range(n):
                while t[i] - t[j] > 5_000_000:
                    j += 1
                peak = max(peak, (i - j) / 5.0)
        brate = f"overall={overall:.1f}Hz peak5s={peak:.1f}Hz nominal={nominal:.1f}Hz ratio_peak={peak/nominal:.2f} flag={peak/nominal>=1.6}"

        # --- inter-beacon arrival timing ---
        gaps = [t[i]-t[i-1] for i in range(1, n)]
        inb = [g for g in gaps if g <= 300_000]
        thr = 0.7 * bi * TU_US
        short = sum(1 for g in inb if g < thr)
        sub = f"sub_frac={short/len(inb):.2f} ({short}/{len(inb)}) flag={len(inb)>=8 and short/len(inb)>0.2}"

        print(f"\n  BSSID {b}  beacons={n}  dur={dur:.0f}s  ch={sorted(d['ch'])}  IE-sets={len(d['ies'])}")
        print(f"     sequence-number : {snd}")
        print(f"     beacon-rate     : {brate}")
        print(f"     inter-beacon    : {sub}")
    print("=" * 70)


if __name__ == "__main__":
    main()
