# The Watcher

The defender half of the project: an ML detector that learns to tell the real
router from the twin, plus the arms-race orchestrator and the kill-switch.

## Setup

A virtualenv is already created at `watcher/.venv` (using ESP-IDF's bundled
Python, kept off Google Drive). To use it:

```powershell
cd C:\Users\souka\AL-GHUL\watcher
.\.venv\Scripts\Activate.ps1
```

If you ever need to recreate it:
```powershell
C:\Espressif\tools\idf-python\3.11.2\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run without hardware (validate the pipeline)

```powershell
python -m pytest -q                        # end-to-end test on synthetic data
python -m src.armsrace --mode synth --rounds 12
```

Outputs: round log in `../experiments/round-logs/`, curve PNG in
`../experiments/plots/`.

## Run live in the lab

Fill `src/config.py` first (your SSID/BSSID, AL-GHUL control URL, sniffer COM
port), then:

```powershell
python -m src.armsrace --mode live --rounds 8 --capture-seconds 20
python -m src.killswitch --image ..\firmware\kill\build\kill.bin --yes
```

## Module map

| File | Role |
|---|---|
| `config.py`    | lab settings (fill these in) |
| `capture.py`   | read the sniffer's JSON stream over serial |
| `features.py`  | records -> feature table (no BSSID-identity leakage) |
| `train.py`     | train the RandomForest Watcher |
| `evaluate.py`  | accuracy / precision / recall / FPR |
| `synth.py`     | synthetic beacons (hardware-free validation + attacker surrogate) |
| `attacker.py`  | evolutionary disguise search (the attack AI) |
| `armsrace.py`  | the round loop (synth or live backend) |
| `plot_curve.py`| the H4 figure |
| `control.py`   | HTTP client to AL-GHUL (/status /disguise /ota) |
| `killswitch.py`| push the kill image over OTA |
