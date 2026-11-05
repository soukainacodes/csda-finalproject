#!/usr/bin/env python3
"""Ambient false-positive sweep: run the clock-skew / rule-1 detectors against every
REAL access point the Watcher hears in the air, and count how many a genuine single
AP trips. This answers the 'you only tested one control AP' critique with a real FPR
over many diverse, genuine radios. Passive, receive-only, own hardware.

Usage:
  python -m experiments.ambient_fpr 180           # capture 180 s live from COM15
  python -m experiments.ambient_fpr - capture.jsonl  # analyse an existing capture
"""
from __future__ import annotations
import sys, json, time, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_BEACONS = 6            # need enough points for an honest clock fit
RMSE_FLAG_US = 10_000      # a genuine single clock fits to tens of us; the exact
                           # clone exploded to 7e10 us. Anything over 1e4 us is "two clocks".
# the lab's own APs (my hotspot + the twin) are NOT ambient genuine APs; exclude them
EXCLUDE_SSIDS = {"Kaffi_FRI"}
EXCLUDE_BSSIDS = {"aa:d0:43:06:46:e1", "02:a1:00:00:00:01"}


def linfit_rmse(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n; my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    slope = sxy / sxx; b = my - slope * mx
    return (sum((ys[i] - (slope * xs[i] + b)) ** 2 for i in range(n)) / n) ** 0.5


def capture(seconds, port="COM15", baud=115200):
    import serial
    recs = []
    ser = serial.Serial()
    ser.port = port; ser.baudrate = baud; ser.timeout = 1
    ser.dtr = False; ser.rts = False
    ser.open()
    print(f"[capture] listening on {port} for {seconds} s ...", flush=True)
    try:
        end = time.time() + seconds
        while time.time() < end:
            raw = ser.readline().decode("utf-8", "ignore").strip()
            if raw.startswith("{"):
                try:
                    o = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if o.get("k") in ("beacon", "probe_resp"):
                    recs.append(o)
    finally:
        ser.close()
    return recs


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "180"
    ts = time.strftime("%Y%m%d-%H%M%S")
    if arg == "-":
        recs = [json.loads(l) for l in Path(sys.argv[2]).read_text(encoding="utf-8",
                errors="replace").splitlines() if l.strip().startswith("{")]
    else:
        recs = capture(float(arg))
        rawpath = HERE / f"ambient-raw-{ts}.jsonl"
        rawpath.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
        print(f"[capture] {len(recs)} beacon/probe records -> {rawpath.name}")

    # group by BSSID (every AP, not just ours)
    per = {}
    for o in recs:
        if o.get("k") != "beacon":
            continue
        b = o.get("bssid")
        if not b or b in EXCLUDE_BSSIDS or o.get("ssid") in EXCLUDE_SSIDS:
            continue
        d = per.setdefault(b, {"ssid": o.get("ssid"), "ts": []})
        if o.get("t") is not None and o.get("tsf") is not None:
            d["ts"].append((o["t"], o["tsf"]))

    # rule-1: how many BSSIDs advertise each SSID (a real SSID -> 1 BSSID normally)
    ssid_bssids = {}
    for b, d in per.items():
        ssid_bssids.setdefault(d["ssid"], set()).add(b)

    rows, flagged = [], 0
    for b, d in per.items():
        if len(d["ts"]) < MIN_BEACONS:
            continue
        xs = [t for t, _ in d["ts"]]; ys = [tsf for _, tsf in d["ts"]]
        rmse = linfit_rmse(xs, ys)
        if rmse is None:
            continue
        flag = rmse > RMSE_FLAG_US
        flagged += flag
        rows.append((d["ssid"], b, len(d["ts"]), rmse, flag))

    rows.sort(key=lambda r: r[3], reverse=True)
    print("\n=== Ambient false-positive sweep: clock-skew per real AP ===")
    print(f"{'SSID':<22}{'BSSID':<20}{'beacons':>8}{'fit RMSE us':>16}  verdict")
    for ssid, b, n, rmse, flag in rows:
        print(f"{(ssid or '(hidden)')[:21]:<22}{b:<20}{n:>8}{rmse:>16.1f}  {'FLAG' if flag else 'clean'}")

    naps = len(rows)
    rmses = [r[3] for r in rows]
    multi = {s: len(bs) for s, bs in ssid_bssids.items() if len(bs) > 1}
    print("\n=== SUMMARY ===")
    print(f"distinct real APs with >= {MIN_BEACONS} beacons: {naps}")
    if rmses:
        print(f"clock-skew fit RMSE across them: min {min(rmses):.1f} us, "
              f"median {st.median(rmses):.1f} us, max {max(rmses):.1f} us")
    print(f"flagged as a twin (RMSE > {RMSE_FLAG_US} us): {flagged} / {naps}  "
          f"=> false-positive rate {flagged/naps if naps else 0:.3f}")
    print(f"SSIDs seen on >1 BSSID (would trip rule-1): "
          f"{multi if multi else 'none (every real SSID on a single BSSID)'}")

    summ = {"captured_records": len(recs), "real_aps": naps,
            "rmse_us": {"min": min(rmses), "median": st.median(rmses), "max": max(rmses)} if rmses else None,
            "flagged": flagged, "false_positive_rate": round(flagged/naps, 4) if naps else None,
            "multi_bssid_ssids": multi,
            "aps": [{"ssid": s, "bssid": b, "beacons": n, "rmse_us": round(r, 1), "flag": f}
                    for s, b, n, r, f in rows]}
    sp = HERE / f"ambient-fpr-summary-{ts}.json"
    sp.write_text(json.dumps(summ, indent=2), encoding="utf-8")
    print(f"\nwrote {sp.name}")


if __name__ == "__main__":
    main()
