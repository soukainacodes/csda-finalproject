"""The autonomous Watcher: detect the twin on its own, then neutralise it.

This closes the loop. Instead of a human deciding to pull the trigger, the
Watcher watches the air, and the moment it is confident a twin is present it
runs the takeover/kill chain by itself, timestamping every step so the whole
event has real numbers: time-to-detect and time-to-neutralise.

Two sources of beacons:
  synth  (default) - no hardware. The twin appears partway through so you can
                     watch (and measure) the Watcher catch it. For the report
                     and a dry-run of the live logic.
  serial           - the real sniffer (config.SNIFFER_SERIAL_PORT).

Two actuators:
  dry-run (default) - log exactly what it WOULD do, touch nothing.
  --arm             - really neutralise: optional OTA takeover (--own-image),
                      then the kill, over AL-GHUL's own control channel.

Outputs (under experiments/):
  killcam-<ts>.jsonl   - every event with a monotonic timestamp (the kill-cam)
  neutralize-<ts>.json - the latency summary (detect / neutralise / total)
  neutralize-<ts>.png  - a timeline figure for the report/slides

Usage:
  python -m src.sentinel --mode synth
  python -m src.sentinel --mode synth --arm --own-image ../firmware/pwned/build/pwned.bin
  python -m src.sentinel --mode serial --arm
"""
import argparse
import json
import time
from pathlib import Path

from . import config, synth
from .features import records_to_frame
from .train import train_from_records

# ---- detection policy ------------------------------------------------------
DETECT_THRESHOLD = 0.80   # a BSSID whose frames are >=80% predicted "twin" ...
MIN_FRAMES       = 4      # ... over at least this many frames ...
CONSECUTIVE_HITS = 2      # ... in this many windows in a row = a confirmed twin.


class SynthSource:
    """A surrogate air. The real router is always there; the twin switches on
    after `twin_appears_at` windows, so the detect-latency clock is meaningful."""
    def __init__(self, twin_appears_at=2, window_frames=12):
        self.n = 0
        self.twin_appears_at = twin_appears_at
        self.window_frames = window_frames
        self.genome = synth.default_genome()

    def window(self):
        self.n += 1
        if self.n <= self.twin_appears_at:
            # real router only (no twin on the air yet)
            return synth._emit(config.REAL_ROUTER_BSSID, config.REAL_ROUTER_SSID,
                               0, self.window_frames, synth.REAL_BI, synth.REAL_JITTER,
                               synth.REAL_RSSI, synth.REAL_IE_SET, synth.REAL_VENDORS,
                               synth.REAL_CAP), self.n == self.twin_appears_at + 1
        recs = synth.generate_round(self.genome, self.window_frames,
                                    config.REAL_ROUTER_SSID, config.REAL_ROUTER_BSSID,
                                    "02:a1:00:00:00:01")
        return recs, (self.n == self.twin_appears_at + 1)


class SerialSource:
    """Real sniffer windows. 8s gives the channel-hopping sniffer time to catch
    enough frames from each AP for a reliable per-window verdict."""
    def __init__(self, seconds=8.0):
        from . import capture
        self._cap = capture.capture_window
        self.seconds = seconds

    def window(self):
        recs = self._cap(self.seconds, config.SNIFFER_SERIAL_PORT, config.SNIFFER_BAUD)
        return recs, False


def _predict_twin_bssids(model, columns, records):
    """Return {bssid: (twin_fraction, n_frames)} for every non-real BSSID."""
    X, _y, groups = records_to_frame(records, config.REAL_ROUTER_BSSID,
                                     config.REAL_ROUTER_SSID)
    if X.empty:
        return {}
    X = X.reindex(columns=columns, fill_value=0)
    preds = model.predict(X)
    agg = {}
    for g, p in zip(groups, preds):
        tw, n = agg.get(g, (0, 0))
        agg[g] = (tw + int(p), n + 1)
    real = (config.REAL_ROUTER_BSSID or "").lower()
    return {b: (tw / n, n) for b, (tw, n) in agg.items() if b != real and n > 0}


class KillCam:
    """Append-only event log with a monotonic clock; also echoes to the console."""
    def __init__(self, path):
        self.path = path
        self.t0 = time.monotonic()
        self.events = []
        path.write_text("", encoding="utf-8")

    def log(self, event, **data):
        t = time.monotonic() - self.t0
        rec = {"t": round(t, 3), "event": event, **data}
        self.events.append(rec)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        tag = {"monitor": "..", "twin_online": "!!", "suspect": "?.",
               "DETECTED": ">>", "takeover": "**", "KILL": "XX",
               "neutralized": "##"}.get(event, "..")
        extra = " ".join(f"{k}={v}" for k, v in data.items())
        print(f"  [{t:7.3f}s] {tag} {event:<12} {extra}")
        return t


def neutralize(killcam, armed, own_image, url, token, ctl="http", ctl_port=None):
    """The autonomous response. Two clean paths:
      - with an OTA payload: reflash the twin into our own firmware. That reflash
        IS the neutralisation (the twin is replaced), so we do NOT kill after.
      - without one: the authenticated kill (death rattle, then self-wipe), over
        WiFi (ctl=http) or over USB (ctl=serial, reliable, no AP join needed).
    """
    from . import control
    if own_image:
        killcam.log("takeover", action="OTA -> owned payload",
                    image=Path(own_image).name, armed=armed)
        if armed:
            try:
                control.push_ota(own_image, url, token)
            except Exception as e:
                killcam.log("takeover", error=str(e))
    else:
        killcam.log("KILL", action="death rattle + self-wipe", via=ctl, armed=armed)
        if armed:
            try:
                if ctl == "serial" and ctl_port:
                    resp = control.send_kill_serial(ctl_port, token)
                    killcam.log("KILL", reply=(resp or "")[:60])
                else:
                    control.send_kill(url, token)
            except Exception as e:
                killcam.log("KILL", error=str(e))


def make_timeline_png(summary, out_png):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False
    t_online = summary["t_twin_online"]
    t_det = summary["t_detected"]
    t_neu = summary["t_neutralized"]
    fig, ax = plt.subplots(figsize=(9.0, 2.9))
    span = max(t_neu, 0.5)
    ax.hlines(1, 0, span + 0.5, color="#d6d4cb", lw=2)
    # label offset: alternate up/down and left/right so close points never collide
    pts = [(t_online, "twin online", "#E11D2A", 22, "left"),
           (t_det, "detected", "#B07D1E", -30, "center"),
           (t_neu, "neutralized", "#12876A", 22, "right")]
    for t, lbl, c, dy, ha in pts:
        ax.plot(t, 1, "o", color=c, ms=12, zorder=3)
        ax.annotate(f"{lbl}\n{t:.2f}s", (t, 1), textcoords="offset points",
                    xytext=(0, dy), ha=ha, fontsize=9.5, color=c, weight="bold")
    # detect bracket below the line, neutralize bracket above it (different heights)
    ax.annotate("", (t_det, 0.72), (t_online, 0.72),
                arrowprops=dict(arrowstyle="<->", color="#B07D1E", lw=1.6))
    ax.text((t_online + t_det) / 2, 0.58,
            f"detect {summary['detect_latency']:.2f}s", ha="center",
            fontsize=9, color="#B07D1E", weight="bold")
    ax.annotate("", (t_neu, 1.30), (t_det, 1.30),
                arrowprops=dict(arrowstyle="<->", color="#12876A", lw=1.6))
    ax.text((t_det + t_neu) / 2, 1.355,
            f"neutralize {summary['neutralize_latency']:.2f}s", ha="center",
            fontsize=9, color="#12876A", weight="bold")
    ax.text(span + 0.45, 0.46,
            f"appear → dead: {summary['total_latency']:.2f}s",
            ha="right", fontsize=10.5, color="#0A0A30", weight="bold")
    ax.set_ylim(0.35, 1.6)
    ax.set_xlim(-0.35, span + 0.6)
    ax.set_yticks([])
    ax.set_xlabel("seconds since the Watcher began hunting")
    ax.set_title("Autonomous neutralization timeline", weight="bold", fontsize=13)
    for s in ("top", "left", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=140)
    plt.close(fig)
    return True


def post_companion(base, key, payload):
    """Push a live status to the audience companion (best-effort)."""
    if not base:
        return
    try:
        import requests
        requests.post(base.rstrip("/") + "/event?key=" + key, json=payload, timeout=4)
    except Exception:
        pass


def run(mode="synth", armed=False, own_image=None, url=None, token=None,
        companion_url=None, companion_key=None, ctl="http", ctl_port=None,
        max_windows=40, poll_gap=0.3):
    ts = time.strftime("%Y%m%d-%H%M%S")
    killcam = KillCam(config.ROUND_LOGS / f"killcam-{ts}.jsonl")
    print(f"\nTHE WATCHER IS HUNTING  (mode={mode}, {'ARMED' if armed else 'dry-run'})\n")
    post_companion(companion_url, companion_key, {"down": False})  # reset the badge

    # 1) train a detector from one reference capture that contains both classes
    src = SynthSource() if mode == "synth" else SerialSource()
    if mode == "synth":
        ref = synth.generate_round(synth.default_genome(), 60, config.REAL_ROUTER_SSID,
                                   config.REAL_ROUTER_BSSID, "02:a1:00:00:00:01", seed=1)
    else:
        print("  capturing a reference window to train the detector...")
        ref, _ = src.window()
    model, metrics, _ = train_from_records(ref, config.REAL_ROUTER_BSSID,
                                           config.REAL_ROUTER_SSID)
    from .train import load_model  # noqa
    columns = config_feature_columns(ref)
    killcam.log("monitor", detector_acc=round(metrics["accuracy"], 3),
                fpr=round(metrics["fpr"], 3))

    # 2) hunt
    t_twin_online = None
    streak = 0
    hit_bssid = None
    for _ in range(max_windows):
        records, twin_just_appeared = src.window()
        if twin_just_appeared and t_twin_online is None:
            t_twin_online = killcam.log("twin_online", note="a twin is now on the air")
        scores = _predict_twin_bssids(model, columns, records)
        best = max(scores.items(), key=lambda kv: kv[1][0] * (kv[1][1] >= MIN_FRAMES),
                   default=None)
        if best and best[1][0] >= DETECT_THRESHOLD and best[1][1] >= MIN_FRAMES:
            streak += 1
            hit_bssid = best[0]
            killcam.log("suspect", bssid=best[0], twin_score=round(best[1][0], 2),
                        frames=best[1][1], streak=streak)
            if streak >= CONSECUTIVE_HITS:
                t_det = killcam.log("DETECTED", bssid=hit_bssid,
                                    confidence=round(best[1][0], 2))
                break
        else:
            streak = 0
        time.sleep(poll_gap)
    else:
        print("\n  no twin confirmed within the window budget.\n")
        return None

    # 3) neutralize (autonomously)
    neutralize(killcam, armed, own_image, url, token, ctl=ctl, ctl_port=ctl_port)
    t_neu = killcam.log("neutralized", target=hit_bssid)

    if t_twin_online is None:
        t_twin_online = 0.0
    summary = {
        "mode": mode, "armed": armed, "target_bssid": hit_bssid,
        "t_twin_online": round(t_twin_online, 3),
        "t_detected": round(t_det, 3),
        "t_neutralized": round(t_neu, 3),
        "detect_latency": round(t_det - t_twin_online, 3),
        "neutralize_latency": round(t_neu - t_det, 3),
        "total_latency": round(t_neu - t_twin_online, 3),
        "detector_accuracy": round(metrics["accuracy"], 3),
        "detector_fpr": round(metrics["fpr"], 3),
    }
    out_json = config.ROUND_LOGS / f"neutralize-{ts}.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    out_png = config.PLOTS / f"neutralize-{ts}.png"
    made = make_timeline_png(summary, out_png)

    post_companion(companion_url, companion_key, {
        "down": True, "detect": summary["detect_latency"],
        "neutralize": summary["neutralize_latency"], "total": summary["total_latency"],
        "target": hit_bssid})

    print("\n  === NEUTRALIZED ===")
    print(f"    twin online -> detected:   {summary['detect_latency']:.2f}s")
    print(f"    detected   -> neutralized: {summary['neutralize_latency']:.2f}s")
    print(f"    total time to kill:        {summary['total_latency']:.2f}s")
    print(f"    detector: acc {summary['detector_accuracy']} / fpr {summary['detector_fpr']}")
    print(f"\n  kill-cam:  {killcam.path}")
    print(f"  summary:   {out_json}")
    if made:
        print(f"  timeline:  {out_png}")
    print()
    return summary


def config_feature_columns(ref_records):
    """The detector's training columns (sorted), derived from the reference set."""
    X, _y, _g = records_to_frame(ref_records, config.REAL_ROUTER_BSSID,
                                 config.REAL_ROUTER_SSID)
    return list(X.columns)


def main():
    ap = argparse.ArgumentParser(description="Autonomous Watcher: detect + neutralise the twin")
    ap.add_argument("--mode", choices=["synth", "serial"], default="synth")
    ap.add_argument("--arm", action="store_true", help="really neutralise (else dry-run)")
    ap.add_argument("--own-image", default=None, help="OTA payload to push before the kill")
    ap.add_argument("--url", default=None, help="override AL-GHUL control URL")
    ap.add_argument("--token", default=None, help="control token (runtime, keeps it out of files)")
    ap.add_argument("--companion-url", default=None,
                    help="push live TARGET DOWN + latency to the audience companion")
    ap.add_argument("--companion-key", default=None, help="companion presenter key")
    ap.add_argument("--ctl", choices=["http", "serial"], default="http",
                    help="how to deliver the kill: http (WiFi) or serial (USB, reliable)")
    ap.add_argument("--ctl-port", default=None, help="AL-GHUL USB port for --ctl serial (e.g. COM12)")
    args = ap.parse_args()
    run(mode=args.mode, armed=args.arm, own_image=args.own_image,
        url=args.url, token=args.token,
        companion_url=args.companion_url, companion_key=args.companion_key,
        ctl=args.ctl, ctl_port=args.ctl_port)


if __name__ == "__main__":
    main()
