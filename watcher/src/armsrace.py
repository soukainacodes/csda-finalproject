"""The arms race: run attacker vs Watcher over rounds and record the curve.

HONEST STATUS: this is the DEMOTED arms-race FRAMEWORK, not a result. On real hardware the
curve stayed FLAT (accuracy ~1.0 every round, no evasion); the only "zig-zag" is the synthetic
run, whose gap is hand-coded in synth.py (circular). In live/serial mode the attacker does NOT
hill-climb on a fitness signal, it just mutates randomly (see set_disguise paths below). Report
this as a framework and a LIMITATION (experiments/ml-watcher-limitations.md), and rest the
detection findings on the measured physical detectors and experiments/ml_real.py.

Each round: apply the attacker's disguise -> capture -> retrain the Watcher on
ALL data so far -> measure detection -> the attacker evolves to evade. The
detection-accuracy curve across rounds is the H4 research result.

Two backends share the exact same loop:
  - synth : no hardware, validates the whole pipeline and produces a demo curve.
  - live  : drives the real AL-GHUL (HTTP /disguise) and the real sniffer (serial).

Run offline now:   python -m src.armsrace --mode synth --rounds 12
Run in the lab:    python -m src.armsrace --mode live  --rounds 8
"""
import argparse
import csv
import json
import time

from . import config
from .train import train_from_records
from .features import records_to_frame
from .evaluate import detection_rate
from .attacker import Attacker
from .synth import generate_round


def genome_to_disguise(g: dict) -> dict:
    """Map the abstract genome to the firmware's /disguise JSON.

    The BSSID is kept FIXED during a live run so disguise changes apply without
    restarting the twin's WiFi (which would drop the control link). The attacker
    still varies beacon interval, TX power, and the vendor IE, which is plenty for
    a measurable arms race on hardware.
    """
    payload = {
        "bssid": "02:a1:00:00:00:01",   # fixed: avoids WiFi restarts mid-run
        "beacon_interval": int(g["beacon_interval"]),
        "tx_power": int(g["tx_power"]),
    }
    if g["vendor_ie"]:
        payload["vendor_ie"] = {"oui": "00:50:f2", "payload_hex": "0050f204"}
    else:
        payload["vendor_ie"] = False
    return payload


class SynthBackend:
    name = "synth"

    def __init__(self, n_each=150):
        self.ssid = config.REAL_ROUTER_SSID if "FILL_ME" not in config.REAL_ROUTER_SSID else "LabNet"
        self.real_bssid = config.REAL_ROUTER_BSSID if "FILL_ME" not in config.REAL_ROUTER_BSSID else "3c:aa:bb:cc:dd:01"
        self.twin_bssid = "02:a1:00:00:00:01"
        self.n_each = n_each
        self.genome = None
        self._seed = 100

    def set_disguise(self, g):
        self.genome = g

    def capture(self):
        self._seed += 1
        return generate_round(self.genome, self.n_each, self.ssid,
                              self.real_bssid, self.twin_bssid, seed=self._seed)

    def fitness_fn(self, model, columns):
        def f(genome):
            recs = generate_round(genome, 80, self.ssid, self.real_bssid,
                                  self.twin_bssid, seed=999)
            X, y, _ = records_to_frame(recs, self.real_bssid, self.ssid)
            twin = X[[yy == 1 for yy in y]]
            if twin.empty:
                return 0.0
            twin = twin.reindex(columns, axis=1, fill_value=0)
            return detection_rate(model, twin)
        return f


class LiveBackend:
    name = "live"

    def __init__(self, capture_seconds=20):
        self.ssid = config.REAL_ROUTER_SSID
        self.real_bssid = config.REAL_ROUTER_BSSID
        self.secs = capture_seconds

    def set_disguise(self, g):
        from .control import push_disguise
        push_disguise(genome_to_disguise(g))
        # The disguise apply restarts the twin's WiFi (~0.5s later), which drops
        # clients. Give AL-GHUL and the laptop time to come back before capturing.
        time.sleep(10)

    def capture(self):
        from .capture import capture_window
        return capture_window(self.secs, config.SNIFFER_SERIAL_PORT, config.SNIFFER_BAUD)

    def fitness_fn(self, model, columns):
        return None  # live: no offline probe; the loop hill-climbs on measurement


class SerialBackend:
    """Drive AL-GHUL over its USB cable (COM for the S3) and capture over the
    sniffer's USB. No WiFi control plane, so the laptop stays on its normal
    network and nothing drops when the twin changes disguise."""
    name = "serial"

    def __init__(self, ctl_port, sniff_port, ctl_baud=115200, sniff_baud=115200,
                 capture_seconds=20):
        self.ssid = config.REAL_ROUTER_SSID
        self.real_bssid = config.REAL_ROUTER_BSSID
        self.sniff_port = sniff_port
        self.sniff_baud = sniff_baud
        self.secs = capture_seconds
        import serial
        self._ser = serial.Serial()
        self._ser.port = ctl_port
        self._ser.baudrate = ctl_baud
        self._ser.timeout = 2
        self._ser.dtr = False
        self._ser.rts = False
        self._ser.open()

    def set_disguise(self, g):
        import json
        payload = genome_to_disguise(g)
        self._ser.reset_input_buffer()
        self._ser.write((json.dumps(payload) + "\n").encode())
        self._ser.flush()
        ok, t0 = False, time.time()
        while time.time() - t0 < 8:
            ln = self._ser.readline().decode("utf-8", "ignore")
            if "DISGUISE_OK" in ln:
                ok = True
                break
        if not ok:
            print("  (warning: no DISGUISE_OK ack; continuing)")
        time.sleep(3)  # let a few beacons go out with the new disguise

    def capture(self):
        from .capture import capture_window
        return capture_window(self.secs, self.sniff_port, self.sniff_baud)

    def fitness_fn(self, model, columns):
        return None


def _twin_detection(model, columns, recs, backend) -> float:
    X, y, _ = records_to_frame(recs, backend.real_bssid, backend.ssid)
    twin = X[[yy == 1 for yy in y]]
    if twin.empty:
        return 0.0
    twin = twin.reindex(columns, axis=1, fill_value=0)
    return detection_rate(model, twin)


def _accuracy_on(model, columns, recs, backend):
    from sklearn.metrics import accuracy_score
    X, y, _ = records_to_frame(recs, backend.real_bssid, backend.ssid)
    if X.empty or len(set(y)) < 2:
        return None
    X = X.reindex(columns, axis=1, fill_value=0)
    return float(accuracy_score(y, model.predict(X)))


def run(backend, rounds=12):
    """One round = one attacker move + one defender response.

    deployed_*  = the detector trained on EARLIER rounds, measured against this
                  round's NEW disguise. This is the arms-race headline: it DIPS
                  when the attacker evades.
    accuracy / retrained_* = after retraining on this round too: the recovery.
    """
    attacker = Attacker()
    all_records = []
    history = []
    deployed_model = None
    deployed_cols = None

    for r in range(rounds):
        # 1) attacker evolves specifically to evade the currently DEPLOYED detector
        if deployed_model is not None:
            fit = backend.fitness_fn(deployed_model, deployed_cols)
            if fit is not None:
                attacker.adapt(fit)
            else:
                attacker.genome = attacker.mutate(attacker.genome)

        g = attacker.propose()
        backend.set_disguise(g)
        recs = backend.capture()

        # 2) evasion: deployed detector vs this new disguise
        dep_acc = _accuracy_on(deployed_model, deployed_cols, recs, backend) if deployed_model else None
        dep_det = _twin_detection(deployed_model, deployed_cols, recs, backend) if deployed_model else None

        # 3) recovery: retrain on everything so far, re-measure
        all_records += recs
        model, metrics, (X, y) = train_from_records(
            all_records, backend.real_bssid, backend.ssid,
            save_path=str(config.MODEL_DIR / f"watcher_round{r:02d}.joblib"))
        cols = list(X.columns)
        retr_det = _twin_detection(model, cols, recs, backend)

        row = {
            "round": r,
            "deployed_accuracy": "" if dep_acc is None else round(dep_acc, 4),
            "deployed_twin_detection": "" if dep_det is None else round(dep_det, 4),
            "accuracy": round(metrics["accuracy"], 4),          # post-retrain, held-out
            "retrained_twin_detection": round(retr_det, 4),
            "precision": round(metrics["precision"], 4),
            "recall": round(metrics["recall"], 4),
            "fpr": round(metrics["fpr"], 4),
            "genome": json.dumps(g),
        }
        history.append(row)
        da = "n/a " if dep_acc is None else f"{dep_acc:.3f}"
        print(f"round {r:2d} | deployed_acc={da} -> retrained_acc={row['accuracy']:.3f} "
              f"| fpr={row['fpr']:.3f} | {g}")

        deployed_model, deployed_cols = model, cols

    _save(history, backend.name)
    return history


def _save(history, tag):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = config.ROUND_LOGS / f"armsrace-{tag}-{stamp}.csv"
    json_path = config.ROUND_LOGS / f"armsrace-{tag}-{stamp}.json"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(history[0].keys()))
        w.writeheader()
        w.writerows(history)
    with open(json_path, "w") as f:
        json.dump(history, f, indent=2)
    print(f"\nsaved round log: {csv_path}")

    try:
        from .plot_curve import plot_from_history
        png = config.PLOTS / f"armsrace-{tag}-{stamp}.png"
        plot_from_history(history, str(png))
        print(f"saved curve:     {png}")
    except Exception as e:
        print(f"(plot skipped: {e})")


def main():
    ap = argparse.ArgumentParser(description="AL-GHUL vs the Watcher arms race")
    ap.add_argument("--mode", choices=["synth", "live", "serial"], default="synth")
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--capture-seconds", type=int, default=20)
    ap.add_argument("--ctl-port", default="COM12", help="AL-GHUL USB port (serial mode)")
    ap.add_argument("--sniff-port", default=config.SNIFFER_SERIAL_PORT,
                    help="sniffer USB port")
    args = ap.parse_args()

    if args.mode == "synth":
        backend = SynthBackend()
    elif args.mode == "live":
        backend = LiveBackend(args.capture_seconds)
    else:  # serial: control over USB, capture over USB, laptop stays on its own net
        backend = SerialBackend(args.ctl_port, args.sniff_port,
                                capture_seconds=args.capture_seconds)
    run(backend, rounds=args.rounds)


if __name__ == "__main__":
    main()
