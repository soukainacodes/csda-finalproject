# Lab runbook (how to run an experiment)

Prerequisite: both boards flashed (see BUILD_AND_FLASH.md) and your own values
filled into `app_config.h` and `watcher/src/config.py`.

## A. Validate the Watcher with no hardware (do this first)

```powershell
cd C:\Users\souka\AL-GHUL\watcher
.\.venv\Scripts\Activate.ps1
python -m pytest -q                       # end-to-end test on synthetic data
python -m src.armsrace --mode synth --rounds 12
```

This produces a round log under `experiments/round-logs/` and the arms-race curve
PNG under `experiments/plots/`. Use it to sanity-check the pipeline and to have a
figure ready even before the lab session.

## B. Live run in the lab

1. Power the sniffer (classic ESP32, COM8). Confirm it streams beacons:
   `python -c "from src.capture import stream; [print(r) for r in stream('COM8',115200)]"`
   (Ctrl+C to stop.)
2. Power AL-GHUL (ESP32-S3). It clones your SSID, brings up its uplink, and starts
   the control server. Note its uplink IP from the serial monitor or your router,
   and set `ALGHUL_CONTROL_URL` in `config.py`.
3. Confirm control: `python -c "from src import control; print(control.get_status())"`.
4. **H1** (auto-join): with AL-GHUL out-signalling, watch your phone associate to
   the twin BSSID (check the phone's WiFi details / your router's client list).
5. **H2** (invisibility): browse on the phone; the relay should keep the internet
   working.
6. **H3 + H4** (detection + arms race):
   ```powershell
   python -m src.armsrace --mode live --rounds 8 --capture-seconds 20
   ```
   Each round applies a disguise to AL-GHUL, captures with the sniffer, retrains
   the Watcher, records accuracy/precision/recall/FPR, and lets the attacker
   evolve. The curve lands in `experiments/plots/`.

## C. The finisher (kill-switch)

When the Watcher is confident, wipe AL-GHUL over its own OTA channel:

```powershell
python -m src.killswitch --image ..\firmware\kill\build\kill.bin --yes
```

AL-GHUL erases its twin slot, saved disguise, and OTA selector, and goes dark.
Revive it later only with a USB re-flash (BUILD_AND_FLASH.md step 3).

## What to collect for the report (the 50%)

- The arms-race curve PNG (the H4 result).
- The per-round CSV/JSON (accuracy, precision, recall, FPR per round).
- Notes/screenshots for H1 (phone auto-join) and H2 (working internet).
- A short account of which disguise knobs the attacker evolved and which residual
  feature let the Watcher recover (expected: beacon-timing jitter floor).
