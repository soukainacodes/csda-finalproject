#!/usr/bin/env python3
"""Evil-twin detector comparison harness (Watcher side).

Reads the on-board Watcher's serial stream for a fixed duration, logs every line
raw, and computes two detectors for the TARGET SSID so they can be compared head
to head against the same ground-truth attacker (AL-GHUL):

  1. RULE-1 (BSSID count): the target SSID heard from >= 2 BSSIDs = twin present.
     Cheap and instant. Fails when the twin clones the exact real BSSID.
  2. CLOCK-SKEW (Jana & Kasera 2010): each AP's TSF clock runs at its own rate.
     We fit the AP's TSF against our local receive time per BSSID. A clone that
     shares a BSSID shows two mixed clocks => a bad single-line fit (high RMSE),
     which rule-1 cannot see. Two separate BSSIDs with clearly different skews
     also confirm two distinct radios.

The ML detector (the RandomForest) runs separately on the same captured beacons.

Lab use only, passive, receive-only. Writes to this folder.

  python watcher_compare.py --port COM15 --secs 120 --scenario A --label "..."
"""
from __future__ import annotations
import argparse, json, time, sys, statistics
from pathlib import Path

try:
    import serial  # pyserial (present in the IDF python env)
except ImportError:
    print("need pyserial: run with the IDF python (it has it)"); sys.exit(1)

TARGET = "Kaffi_FRI"
HERE = Path(__file__).resolve().parent


def linfit(xs, ys):
    """Least-squares slope/intercept + RMSE of ys ~ slope*xs + b."""
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True)
    ap.add_argument("--secs", type=int, default=120)
    ap.add_argument("--scenario", default="X")
    ap.add_argument("--label", default="")
    ap.add_argument("--real-bssid", default="", help="known real-AP BSSID, for labelling only")
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    raw_path = HERE / f"watcher-raw-{args.scenario}-{stamp}.jsonl"
    sum_path = HERE / f"watcher-summary-{args.scenario}-{stamp}.json"

    try:
        ser = serial.Serial(args.port, 115200, timeout=1)
        ser.dtr = False; ser.rts = False          # S3 USB-JTAG: do NOT reset the board
    except Exception as e:
        print(f"could not open {args.port}: {e}"); sys.exit(1)

    # per-BSSID clock samples for the target SSID; detection timeline from the board
    samples: dict[str, list[tuple[int, int, int]]] = {}   # bssid -> [(t_local, tsf, rssi)]
    detect_events = []                                     # (t, state)
    sec_bins: dict[int, set] = {}                          # second -> set of live bssids (rule-1 timeline)

    print(f"[*] capturing {args.secs}s from {args.port}  scenario={args.scenario}  -> {raw_path.name}")
    end = time.time() + args.secs
    raw = raw_path.open("w", encoding="utf-8")
    first_t = None
    while time.time() < end:
        line = ser.readline().decode("utf-8", "replace").strip()
        if not line or not line.startswith("{"):
            continue
        raw.write(line + "\n")
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = o.get("k")
        if k == "detect":
            detect_events.append((o.get("t"), o.get("state")))
        elif k in ("beacon", "probe_resp") and o.get("ssid") == TARGET:
            b = o.get("bssid"); t = o.get("t"); tsf = o.get("tsf"); rssi = o.get("rssi")
            if b is None or t is None or tsf is None:
                continue
            if first_t is None:
                first_t = t
            samples.setdefault(b, []).append((t, tsf, rssi))
            sec_bins.setdefault((t - first_t) // 1_000_000, set()).add(b)
    raw.close(); ser.close()

    # ---- RULE-1: fraction of 1s bins that saw >= 2 BSSIDs of the target SSID ----
    bins = sorted(sec_bins)
    rule1_hits = sum(1 for s in bins if len(sec_bins[s]) >= 2)
    rule1_rate = (rule1_hits / len(bins)) if bins else 0.0
    rule1_ttd = next((s for s in bins if len(sec_bins[s]) >= 2), None)  # seconds to first detect

    # ---- CLOCK-SKEW: per-BSSID slope (ppm) + single-line fit RMSE ----
    skew = {}
    for b, pts in samples.items():
        ts = [p[0] for p in pts]; tsfs = [p[1] for p in pts]
        fit = linfit(ts, tsfs)
        if fit:
            slope, _, rmse = fit
            skew[b] = {"n": len(pts), "skew_ppm": round((slope - 1.0) * 1e6, 1),
                       "fit_rmse_us": round(rmse, 1), "rssi_med": statistics.median(p[2] for p in pts)}
        else:
            skew[b] = {"n": len(pts), "skew_ppm": None, "fit_rmse_us": None,
                       "rssi_med": (statistics.median(p[2] for p in pts) if pts else None)}

    summary = {
        "scenario": args.scenario, "label": args.label, "ts": stamp, "secs": args.secs,
        "target_ssid": TARGET, "real_bssid_hint": args.real_bssid,
        "n_bssids_seen": len(samples), "bssids": list(samples.keys()),
        "rule1": {"detection_rate": round(rule1_rate, 3), "time_to_detect_s": rule1_ttd,
                  "bins": len(bins), "hit_bins": rule1_hits},
        "clock_skew": skew,
        "board_detect_events": detect_events,
        "raw_file": raw_path.name,
    }
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[*] raw     -> {raw_path.name}")
    print(f"[*] summary -> {sum_path.name}")
    print(f"    rule-1 BSSIDs seen: {len(samples)}  detection_rate={rule1_rate:.0%}  ttd={rule1_ttd}s")
    for b, s in skew.items():
        print(f"    clock-skew {b}: n={s['n']} skew={s['skew_ppm']}ppm fit_rmse={s['fit_rmse_us']}us rssi~{s['rssi_med']}")


if __name__ == "__main__":
    main()
