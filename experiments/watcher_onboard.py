#!/usr/bin/env python3
"""Capture the Watcher's OWN on-board verdict, live, and save it to a file.

Unlike watcher_compare.py / detector_analysis*.py (which judge the Watcher's data
offline in Python), this records what the ESP32 Watcher itself decides in real
time: the {"k":"detect",...} lines its firmware emits (rule-1 + IE-fingerprint +
TSF monotonicity), plus the target-SSID beacons it heard. One run per scenario.

Saves:
  watcher-onboard-raw-{scenario}-{stamp}.jsonl   every serial line (the raw log)
  watcher-onboard-sum-{scenario}-{stamp}.json    transitions + verdict

Lab use only, passive, receive-only. S3 USB-JTAG: dtr/rts stay low (no reset).

  python watcher_onboard.py --port COM15 --secs 60 --scenario B --label "twin clones aa:d0 + real AP"
"""
from __future__ import annotations
import argparse, json, time, sys, collections
from pathlib import Path

try:
    import serial
except ImportError:
    print("need pyserial (run with the IDF python)"); sys.exit(1)

TARGET = "Kaffi_FRI"
HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default="COM15")
    ap.add_argument("--secs", type=int, default=60)
    ap.add_argument("--scenario", default="X")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    raw_path = HERE / f"watcher-onboard-raw-{args.scenario}-{stamp}.jsonl"
    sum_path = HERE / f"watcher-onboard-sum-{args.scenario}-{stamp}.json"

    try:
        s = serial.Serial(); s.port = args.port; s.baudrate = 115200; s.timeout = 1
        s.dtr = False; s.rts = False; s.open()
    except Exception as e:
        print(f"could not open {args.port}: {e}"); sys.exit(1)

    print(f"[*] scenario {args.scenario}: {args.label}")
    print(f"[*] capturing {args.secs}s of the Watcher's OWN verdict from {args.port}")

    transitions = []                      # (t_elapsed, state, reasons, live_bssids, bssids)
    bss = collections.defaultdict(lambda: {"ch": set(), "ies": set(), "n": 0})
    reasons_seen = set()
    t0 = time.time()
    with raw_path.open("w", encoding="utf-8") as raw:
        while time.time() - t0 < args.secs:
            ln = s.readline().decode("utf-8", "replace").strip()
            if not ln.startswith("{"):
                continue
            raw.write(ln + "\n")
            try:
                o = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if o.get("k") == "detect":
                el = round(time.time() - t0, 1)
                st = o.get("state"); rs = o.get("reasons") or []
                transitions.append((el, st, rs, o.get("live_bssids"), o.get("bssids")))
                for r in rs:
                    reasons_seen.add(r)
                print(f"    [{el:5.1f}s] {st}  reasons={rs}  live_bssids={o.get('live_bssids')}", flush=True)
            elif o.get("k") == "beacon" and o.get("ssid") == TARGET:
                b = o["bssid"]; d = bss[b]; d["n"] += 1
                d["ch"].add(o.get("ch")); d["ies"].add(tuple(o.get("ies", [])))
    s.close()

    any_detected = any(t[1] == "DETECTED" for t in transitions)
    ends_detected = transitions[-1][1] == "DETECTED" if transitions else None
    verdict = ("DETECTED" if any_detected else "CLEAR (no detection emitted)")

    summary = {
        "scenario": args.scenario, "label": args.label, "ts": stamp, "secs": args.secs,
        "target_ssid": TARGET,
        "on_board_verdict": verdict,
        "any_detected": any_detected, "ends_detected": ends_detected,
        "reasons_seen": sorted(reasons_seen),
        "n_transitions": len(transitions),
        "transitions": [{"t": t[0], "state": t[1], "reasons": t[2],
                         "live_bssids": t[3], "bssids": t[4]} for t in transitions],
        "kaffi_bssids": {b: {"n": d["n"], "channels": sorted(x for x in d["ch"] if x is not None),
                             "distinct_ie_sets": len(d["ies"])} for b, d in bss.items()},
        "raw_file": raw_path.name,
    }
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[*] Kaffi_FRI BSSIDs heard:")
    for b, d in bss.items():
        print(f"      {b}  n={d['n']}  ch={sorted(x for x in d['ch'] if x is not None)}  distinct_IE_sets={len(d['ies'])}")
    print(f"[*] ON-BOARD VERDICT: {verdict}   reasons_seen={sorted(reasons_seen)}")
    print(f"[*] raw -> {raw_path.name}")
    print(f"[*] sum -> {sum_path.name}")


if __name__ == "__main__":
    main()
