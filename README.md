<div align="center">

```
            █████╗ ██╗      ██████╗ ██╗  ██╗██╗   ██╗██╗
           ██╔══██╗██║     ██╔════╝ ██║  ██║██║   ██║██║
           ███████║██║     ██║  ███╗███████║██║   ██║██║
           ██╔══██║██║     ██║   ██║██╔══██║██║   ██║██║
           ██║  ██║███████╗╚██████╔╝██║  ██║╚██████╔╝███████╗
           ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
                      v s   t h e   W A T C H E R
```

### A machine-learning detector versus a shape-shifting rogue access point, measured as an arms race on real hardware.

`الغول` &nbsp;·&nbsp; *al-ghūl*, the desert demon that takes a familiar shape to lure travellers, then strikes.

![ESP-IDF](https://img.shields.io/badge/ESP--IDF-v5.2.8-red)
![ESP32](https://img.shields.io/badge/hardware-ESP32--S3%20%2B%20ESP32-black)
![Python](https://img.shields.io/badge/Watcher-Python%203.11-blue)
![ML](https://img.shields.io/badge/detector-RandomForest-green)
![scope](https://img.shields.io/badge/scope-isolated%20home%20lab-sand)
![no--deauth](https://img.shields.io/badge/no%20deauth-%20no%20jamming-important)

</div>

---

> **Final project, T-742-CSDA, Computer Security: Defence Against the Dark Arts (Reykjavík University).**
> The contribution is the **defender**: an ML detector that learns to unmask a WiFi twin from its radio
> fingerprint, and a **measured attacker-vs-defender study** running on physical ESP32 boards. The evil
> twin is only the adversary the detector is trained and scored against.

## The one line

A rogue access point (**AL-GHŪL**, on an ESP32-S3) clones a network's name and **out-signals** the real
one so a phone roams onto it on its own, then relays traffic transparently so nothing looks wrong. A second
ESP32 sniffs the air and feeds **the Watcher**, a machine-learning classifier that learns to tell the twin
from the real access point. Attacker and defender are then run against each other over rounds, and detection
is measured. No deauthentication, no jamming, ever: the twin only broadcasts and relays.

> **Why this isn't "just an evil twin."** Evil twins are old. The work here is the **ML detector**, the
> **adaptive attacker/defender loop**, the fact that it all runs on **real hardware** (not a simulation),
> and the **authenticated kill-switch** plus the **hardware secret-extraction** finding below.

## Results, on real hardware

Measured on an isolated lab: a phone hotspot as the real AP, a tablet as the only victim, two ESP32 boards.

| Hypothesis | Result |
|---|---|
| **H1 — trust / auto-join** | Devices roamed to the twin on their own; it out-signalled the real AP by **~10 dB** (−64 vs −74 dBm). No deauth. |
| **H2 — invisible interception** | The victim on the twin kept **fully working internet** through the NAT relay. Nothing looked wrong. |
| **H3 — detectability** | The Watcher separated twin from real AP: **accuracy 1.00, precision 1.00, recall 1.00, false-positive rate 0.00** on 98 live beacons. |
| **H4 — the arms race** | Over 6 live rounds the Watcher held **100% / 0% FPR**: the real ESP32 twin could not evade. The synthetic run (`--mode synth`) shows the full **evasion → retrain → recovery** zig-zag for when an attacker *can* approach the real fingerprint. |

Curves and per-round logs live in [`experiments/`](experiments/).

## The finisher, and an honest twist

- **Authenticated kill-switch.** Once the Watcher is confident, the operator sends an authenticated command
  over AL-GHŪL's own control channel (`/kill?token=...`); the board erases its flash and goes dark.
- **...which a flash dump defeats.** AL-GHŪL runs with flash encryption **off** (the ESP32 default). An
  `esptool read_flash` over the chip's debug interface recovers the token **and** the WiFi password **in
  plaintext**. The "authentication" is only as strong as the microcontroller's secret storage, and by
  default that storage is an open book. Mitigation: flash encryption + secure boot; never hardcode secrets.
  *(This is why nothing in this repo is hardcoded, see `app_config.h`.)*

## Architecture

```
                 2.4 GHz beacons
  [ Real AP ] -----------------\
       ^  (uplink STA)          \        USB serial (one JSON record per frame)
       |                         v       +---------------------------+
  [ AL-GHUL  ESP32-S3 ] <~beacons~>  [ Sniffer ESP32 ] -----------> [ Laptop: the Watcher ]
   - clones SSID, out-signals        (promiscuous, RX-only)          - features (no BSSID leak)
   - STA uplink + NAT relay (MITM)                                   - RandomForest detector
   - live disguise (beacon/IE/power)                                 - arms-race orchestrator
   - HTTP + USB control, OTA, /kill  <--- disguise / kill (control) ---- evolutionary attacker
       ^
       | same SSID + PSK (so the victim roams seamlessly)
  [ Victim phone/tablet ] auto-joins the louder twin, internet still works
```

## Repository layout

```
firmware/
  al_ghul/      the twin (ESP32-S3): clone + out-signal + NAT relay + disguise + control + OTA + /kill
  sniffer/      the eyes (classic ESP32): promiscuous capture -> JSON over USB
  kill/         the OTA kill image (wipes flash, goes dark)
  activate-idf.ps1   ESP-IDF environment helper (this machine)
watcher/
  src/          capture, features, RandomForest detector, metrics, evolutionary attacker,
                arms-race loop (synth | live | serial backends), plot, kill-switch client
  tests/        end-to-end pipeline test on synthetic data
experiments/    round logs (CSV) + the detection curves (PNG)
docs/           ETHICS, ARCHITECTURE, BUILD_AND_FLASH, LAB_RUNBOOK, BUILD_LOG
```

## Quick start

```bash
# Watcher (no hardware needed): validate the pipeline and make a demo curve
cd watcher
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m src.armsrace --mode synth --rounds 12
```

Firmware build + flash and the full lab run are in [`docs/BUILD_AND_FLASH.md`](docs/BUILD_AND_FLASH.md)
and [`docs/LAB_RUNBOOK.md`](docs/LAB_RUNBOOK.md). Fill your own values into `firmware/al_ghul/main/app_config.h`
and `watcher/src/config.py` first (nothing is committed with real secrets).

## Scope and ethics

Runs **only** on the author's own gear, an isolated home lab, with her own devices as the only targets.
**No deauthentication, no jamming**, the twin only broadcasts and relays, and the relay does **not** capture
or inspect any payloads. The kill-switch is an authenticated command to the author's **own** board, not a
break-in. Full statement in [`docs/ETHICS.md`](docs/ETHICS.md).

---

<div align="center">

*Al-Ghūl is the shape-shifting demon of Arabic folklore, origin of the English "ghoul" and of the star name
**Algol**, "the demon star." The Watcher is the one who stands guard and sees through the disguise.*

**Soukaina** · MSc · RU · academic project

</div>
