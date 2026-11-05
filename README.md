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

### An on-device, measured comparison of Wi-Fi evil-twin detectors, including the exact-BSSID clone that the naive rule misses.

`الغول` &nbsp;·&nbsp; *al-ghūl*, the desert demon that takes a familiar shape to lure travellers, then strikes.

![ESP-IDF](https://img.shields.io/badge/ESP--IDF-v5.2.8-red)
![ESP32](https://img.shields.io/badge/hardware-ESP32--S3%20%2B%20ESP32-black)
![Python](https://img.shields.io/badge/Watcher-Python%203.11-blue)
![detectors](https://img.shields.io/badge/detectors-10%20compared-green)
![scope](https://img.shields.io/badge/scope-isolated%20home%20lab-sand)
![no--deauth](https://img.shields.io/badge/no%20deauth-%20no%20jamming-important)

</div>

---

> **Final project, T-742-CSDA, Computer Security: Defence Against the Dark Arts (Reykjavík University).**
> The contribution is the **defender**: a measured comparison of evil-twin detectors run **live on a second
> ESP32**, that catches even a twin which clones the real BSSID exactly, the case a simple BSSID-count rule
> is blind to. The evil twin (**AL-GHŪL**) is only the adversary the detectors are scored against.

## The one line

A rogue access point (**AL-GHŪL**, on an ESP32-S3) clones a network's name and **out-signals** the real one
so a phone roams onto it on its own, then relays traffic so nothing looks wrong. A second ESP32 (**the
Watcher**) sniffs the air and runs several detectors on the board; they are compared head-to-head against the
same ground-truth attacker across three scenarios, and the exact-BSSID clone that defeats the naive rule is
caught by the **physical** tells (two clocks under one identity, double beacon rate, a second sequence
counter) that an attacker cannot fake. No deauthentication, no jamming, ever.

---

## Navigate

| Section | What is there |
|---|---|
| [Results (honest)](#results-honest) | the measured findings, with links to the raw logs |
| [Reproduce at home, by case](#reproduce-at-home-by-case) | copy-paste commands for every experiment |
| [Repository map](#repository-map) | what lives in each folder |
| [Scope and ethics](#scope-and-ethics) | lab-only, no deauth/jamming, authorised coursework |
| [Honest limits](#honest-limits) | what this does **not** prove |
| [Docs](#docs) | deeper write-ups |

**Jump to a result or its evidence**
- Detector comparison (all 10 across scenarios A/B/C): [`experiments/master-detector-comparison.md`](experiments/master-detector-comparison.md)
- On-board live sweep + time-to-detect: [`experiments/onboard-results-2026-11-05.md`](experiments/onboard-results-2026-11-05.md)
- The ML, honestly scoped: [`experiments/ml-real-results.md`](experiments/ml-real-results.md), [`experiments/ml-watcher-limitations.md`](experiments/ml-watcher-limitations.md)
- Data augmentation side experiment: [`experiments/ml-aug-results.md`](experiments/ml-aug-results.md)
- Protected-environment measurements (eFuse, flash dump): [`experiments/protected-env/`](experiments/protected-env/)
- Every raw capture and per-run verdict: [`experiments/`](experiments/) (`watcher-raw-*.jsonl`, `watcher-onboard-*`)

---

## Results (honest)

Measured on an isolated lab: a laptop/phone hotspot as the real AP, a tablet as the only victim, two ESP32
boards. Ground-truth scenarios: **A** twin on its own BSSID, **B** twin clones the real BSSID exactly,
**C** a single AP (control).

### The attack works, silently
| Hypothesis | Result | Evidence |
|---|---|---|
| **H1, auto-join** | the tablet roamed to the twin on its own when it out-signalled the real AP (~10 dB). No deauth. | `experiments/` |
| **H2, invisible interception** | the victim on the twin kept **working internet** through the NAT relay; nothing looked wrong. | live |
| **H5, which lock holds** | the silent hands-free re-join still works on **WPA2 and WPA2+PMF**; WPA3-SAE stops the *silent* re-join, but the shared café password is still public. | [`Task2-SecurityModes`](experiments/) |

### Detection, the real contribution
Ten detectors compared against the same twin, across A/B/C. The headline: a simple **BSSID-count rule is
blind to the exact clone (B)**; the clone is caught only by the **physical / device-independent** detectors.

| Detector | A (own BSSID) | B (exact clone) | C (control) | Notes |
|---|---|---|---|---|
| rule-1 (BSSID count) | DETECT | **MISS** | clear | blind to the exact clone |
| clock-skew (TSF fit) | DETECT | **DETECT** | clear | fit RMSE explodes 9 orders for the clone |
| TSF-jump | clear | **DETECT** | clear | two clocks under one BSSID, device-independent |
| IE-fingerprint | differ | **DETECT** | clear | flattered by a bare-ESP32 vs a rich Windows AP |
| sequence-number | blind\* | **DETECT** | clear | two counters; device-independent (channel-locked) |
| beacon-rate | blind\* | **DETECT (2.01x)** | clear | exactly double; device-independent (channel-locked) |
| ensemble | 0.40 | **0.80** | 0.03 | one score, clean separation |

\* blind only while the Watcher channel-hops; measured once both radios sit co-channel. Full table and honest
failure modes: [`experiments/master-detector-comparison.md`](experiments/master-detector-comparison.md).

- **Caught live, on the board.** The detectors run on the second ESP32 (LED red on detect). Across A/B/C it
  detects the clone and does not false-alarm on a lone AP; **detection latency median 3 s (range 2–10 s, n=9)**.
  Confirmed under WPA2 and WPA2+PMF. See [`experiments/onboard-results-2026-11-05.md`](experiments/onboard-results-2026-11-05.md).
- **The un-evadable core is device-independent:** two clocks under one BSSID (TSF-jump on the board,
  clock-skew fit offline), double beacon rate, a second sequence counter (both measured offline, co-channel).
  The IE and per-radio-skew tells are **flattered** by this attacker being a bare ESP32 against a rich
  Windows hotspot, stated plainly, not hidden.

### The machine-learning detector, honestly scoped
A RandomForest trained on the **real** captures (no synthetic data, no BSSID/MAC as a feature) separates twin
from real at 100% with zero false positives, **but with two radios that is separability, not generalization.**
Its value is that it **independently ranks the same physical tells** (clock-skew, IE, timing) the hand
detectors use. The **AI-vs-AI arms race** ran as a **framework**; on this hardware the disguise space was too
coarse to evade, so the curve stayed flat and we report it as a **limitation**, not a result. See
[`experiments/ml-real-results.md`](experiments/ml-real-results.md) and the self-critique
[`experiments/ml-watcher-limitations.md`](experiments/ml-watcher-limitations.md).

### The finisher, and why it is weak
When the Watcher is confident, the operator sends an **authenticated** `KILL` to AL-GHŪL's own control channel
and the board wipes its flash. It works **only because the twin is defenceless**: reading its eFuses shows
**flash encryption off, Secure Boot off, JTAG enabled** (on both boards), and a 4 MB `esptool read_flash`
recovers the Wi-Fi password and the kill token **in plaintext**. A **hardened** twin (flash encryption +
Secure Boot + signed OTA) would survive both, so the same hardening that protects honest IoT would also shield
a well-built rogue, which is why **detection** and **physical response** are what matter. Measurements:
[`experiments/protected-env/`](experiments/protected-env/).

---

## Reproduce at home, by case

**You need:** two ESP32 boards (one ESP32-S3 for the twin, one ESP32/-S3 for the Watcher), ESP-IDF v5.2.8, a
laptop, a phone or tablet as the victim, and a Wi-Fi hotspot you own as the "real" AP. **Set your own values**
in [`firmware/al_ghul/main/app_config.h`](firmware/al_ghul/main/app_config.h) (SSID, password, control token)
and `watcher/src/config.py` before flashing. Flash: see [`docs/BUILD_AND_FLASH.md`](docs/BUILD_AND_FLASH.md).

### Case 0, no hardware: validate the Watcher pipeline
```bash
cd watcher
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q
```

### Case A/B/C, the detector comparison (the headline)
Flash the twin and the Watcher, bring up your real AP, then record the Watcher's live verdict per scenario:
```bash
# from the IDF python (has pyserial); COM15 = Watcher
python experiments/watcher_onboard.py --port COM15 --secs 60 --scenario B --label "exact clone"
```
Change the twin's BSSID over serial to switch scenario (A = own BSSID `02:a1...`, B = clone the real BSSID).
**Result:** `experiments/watcher-onboard-raw-<scn>-*.jsonl` (every frame) + `-sum-*.json` (the verdict:
DETECTED/CLEAR, reasons, time-to-detect). Compare offline with the detector scripts:
```bash
python experiments/detector_analysis.py     # RSSI-bimodality, multi-channel, TSF-jump, sequence-number
python experiments/detector_analysis2.py    # IE-fingerprint, beacon-rate, inter-beacon, ensemble
python experiments/analyze_chlock.py experiments/watcher-onboard-raw-ChLock6-*.jsonl   # channel-locked
```

### Case, security modes (does detection survive WPA2 / PMF / WPA3?)
Over the twin's serial: `AUTHMODE WPA2 | WPA2-PMF | WPA3`, then run the Case-B capture again.
**Result:** `experiments/watcher-onboard-*-Sec*`. (WPA3 note: our twin would not beacon capturably in
WPA3-SAE, an honest gap.)

### Case, the machine-learning detector
```bash
.venv/Scripts/python experiments/ml_real.py   # RF on the real captures: metrics + feature importances
.venv/Scripts/python experiments/ml_aug.py    # augmentation side experiment
.venv/Scripts/python -m src.armsrace --mode synth --rounds 12   # the arms-race FRAMEWORK (synthetic)
```
**Result:** printed metrics, `experiments/plots/fig_ml.png`, and the honest write-ups linked above.

### Case, the danger demos (educational, lab-only, against self-contained fake sites)
```bash
python gateway/dns_helper.py --captive      # OS-probe redirect for the captive portal
python gateway/portal_social.py             # the fake login page (watermarked, throwaway creds)
python gateway/demo_session.py              # the session-cookie replay / 2FA-bypass demo (self-contained)
```
**Result:** `experiments/portal-creds.jsonl`, `experiments/session-hijack-demo-*.log`.

### Case, the protected environment (read-only, no eFuse burning)
```bash
python -m espefuse --chip esp32s3 -p COM18 summary         # flash enc / secure boot / JTAG state
python -m esptool --chip esp32s3 -p COM18 read_flash 0x0 0x400000 dump.bin   # then search for your secrets
python -c "print(open('dump.bin','rb').read().count(b'YOUR_PSK'))"
```
**Result:** `experiments/protected-env/` (eFuse summaries, recovered-secrets evidence, kill-auth test).

---

## Repository map

```
firmware/
  al_ghul/      the twin (ESP32-S3): clone + out-signal + NAT relay + disguise + control + /kill
                app_config.h  <- SET YOUR OWN SSID / PSK / control token here
  sniffer/      the Watcher (ESP32-S3): promiscuous capture + on-board detectors (rule-1, IE, TSF) -> LED + JSON
  kill/         the OTA kill image
  pwned/        the optional "owned" takeover banner image (lab-only demo)
gateway/        educational lab demos: captive portal, DNS helper, session-hijack demo, metadata harvest
watcher/
  src/          capture, features, RandomForest detector, metrics, evolutionary attacker, arms-race loop
  tests/        end-to-end pipeline test on synthetic data
experiments/    ALL the raw logs + per-run verdicts + analysis scripts + result write-ups + figures
  protected-env/  the eFuse / flash-dump / kill-auth measurements
  round-logs/     the arms-race round logs (framework)
docs/           ARCHITECTURE, HOW_IT_WORKS, BUILD_AND_FLASH, LAB_RUNBOOK, ETHICS, MCU_SECURITY, BUILD_LOG
companion-server/  optional web viewer for the deck/dashboard (not required to reproduce anything)
```

---

## Scope and ethics

Runs **only** on the author's own gear, an isolated home lab, with her own devices as the only targets.
**No deauthentication, no jamming**; the twin only broadcasts and relays, and the relay does **not** inspect
payloads. The danger demos run against **self-contained fake sites** written for this project, with throwaway
credentials. The kill is an authenticated command to the author's **own** board, not a break-in. This is
authorised coursework for an academic security module. Full statement: [`docs/ETHICS.md`](docs/ETHICS.md).

> **Note on secrets.** `app_config.h` contains **lab throwaway** values (`bestcoffee`, `backhaul2026`, the
> control token). They unlock only the author's disposable demo network and mean nothing elsewhere. If you
> reproduce this, **replace them with your own**, do not reuse them.

---

## Honest limits

- **Single-pair case study.** One Watcher, one real AP (a laptop hotspot), one twin. Every number is those
  two radios; this is separability, not proof it generalizes to new hardware.
- **The laptop flatters the config detectors.** A rich Windows softAP against a bare ESP32 makes the IE and
  per-radio-skew gaps large; the detectors that would survive a careful clone are the **device-independent**
  ones (two clocks, double beacon rate, sequence number).
- **Detection is not prevention, and no clean evasion run.** The Watcher proves a twin is detectable; it does
  not un-join a victim who already fell, and the kill only works on an unprotected board. The one attempt to
  evade the config tell (vendor IE) crashed the twin's beacon, so "the clock detectors are unevadable" is an
  argument plus a device-independent measurement, not a head-to-head.
- **WPA3 detection not measured.** The twin did not beacon capturably in WPA3-SAE on this ESP32.
- **The ML is a framework and a limitation**, not a validated detector (synthetic separation, flat arms-race
  curve, two-device scope).

---

## Docs

- [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) plain-language walkthrough
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) the rig and the data flow
- [`docs/BUILD_AND_FLASH.md`](docs/BUILD_AND_FLASH.md) building and flashing the two boards
- [`docs/LAB_RUNBOOK.md`](docs/LAB_RUNBOOK.md) the full lab run, step by step
- [`docs/MCU_SECURITY.md`](docs/MCU_SECURITY.md) why a microcontroller needs a protected environment (CVEs)
- [`docs/ETHICS.md`](docs/ETHICS.md) scope and safety

---

## Get the code

<div align="center">

**Scan to clone and reproduce the whole project.**

<img src="docs/qr-github.png" alt="github.com/soukainacodes/csda-finalproject" width="200">

[`github.com/soukainacodes/csda-finalproject`](https://github.com/soukainacodes/csda-finalproject)

</div>

---

<div align="center">

*Al-Ghūl is the shape-shifting demon of Arabic folklore, origin of the English "ghoul" and of the star name
**Algol**, "the demon star." The Watcher is the one who stands guard and sees through the disguise.*

**Soukaina** · MSc · Reykjavík University · academic project

</div>
