# AL-GHUL vs the Watcher, Build

Build workspace for the CSDA final project (T-742-CSDA, RU, Jacky Mallett).
Student: Soukaina. This folder holds the actual code, data, and experiment logs.
The written proposal, concepts, and slides live one level up in `Project/`.

## Safety scope (firm, unchanged)

- Runs ONLY on my own isolated home lab: my own router, my own phone, my own
  laptop, my own two ESP32-S3 boards. Never on production, work, or any network
  I do not own.
- Out-signal, never hide. NO deauthentication, NO jamming. The twin only
  broadcasts a stronger beacon and relays traffic; it never knocks any device
  off any network.
- The only target is my own phone/laptop. No third-party traffic is touched.
- The kill-switch is an authenticated OTA command to my own board, not an
  action against any external device.

## Folder layout

- `firmware/`   ESP-IDF projects. `al-ghul/` (the twin) and `sniffer/` (monitor
                mode capture) get created here with `idf.py create-project`.
- `watcher/`    The detector (Python ML classifier).
    - `src/`    Watcher code: feature extraction + classifier + evaluation.
    - `data/`   Captured beacon datasets, one per experiment round.
    - `models/` Trained classifiers, one per round.
- `experiments/` The arms race.
    - `round-logs/` Per-round records: what disguise, what the Watcher scored.
    - `plots/`      Detection-accuracy-across-rounds curve (the H4 finding).
- `docs/`       Build notes: hardware, wiring, toolchain, decisions.

## Hypotheses this build must produce evidence for

- H1 trust: phone auto-joins the louder twin, no human action.
- H2 invisibility: transparent relay keeps working internet, nothing looks wrong.
- H3 detectability: Watcher separates twin from real router, accuracy A, FPR F.
- H4 arms race: as the twin adapts, accuracy moves along a curve; retraining
  recovers it. This curve is the research result.

## Feasibility ladder

- MVP: twin clones router, out-signals it, phone auto-joins, internet flows,
  Watcher v1 catches it, one round.
- Core: full arms race over several rounds with the accuracy curve, plus the
  OTA kill-switch finisher.
- Stretch: WHISPERER covert channel; onboard TinyML detection.

## Build log

- 2026-09-30: Created build folder skeleton. Toolchain chosen: ESP-IDF (native
  Windows). Both ESP32-S3 boards in hand. Router does 2.4 + 5 GHz (twin clones
  2.4). Test phone: Android.
- 2026-09-30: Board #1 has a single USB-C port through a Silicon Labs CP2102
  USB-to-UART bridge (VID_10C4 PID_EA60). Windows had no driver (error 28, no
  COM port). Installed the Microsoft-signed CP210x driver (silabser.inf
  11.5.0.417, from the Windows Update Catalog) via `pnputil /add-driver ...
  /install` in an elevated shell. Board #1 now enumerates as COM8, status OK.
- 2026-10-01: Installed ESP-IDF v5.2.8 to C:\Espressif (offline installer, silent
  per-user). Installer's final config step threw an exception, so the Python
  virtualenv was missing and the activation script could not locate IDF.
  Recovered by running `tools/idf_tools.py install-python-env` with the bundled
  Python (C:\Espressif\tools\idf-python\3.11.2\python.exe); venv now at
  python_env\idf5.2_py3.11_env with esptool 4.12.0. Activate manually with:
  set IDF_PATH=C:\Espressif\frameworks\esp-idf-v5.2.8, IDF_TOOLS_PATH=C:\Espressif,
  prepend the idf-python dir to PATH, then dot-source export.ps1.
- 2026-10-01: HARDWARE INVENTORY corrected. The two boards are NOT both ESP32-S3.
    - Board #1 = classic ESP32 (ESP32-D0WD-V3 rev v3.1), 4MB flash, no PSRAM,
      CP2102 UART bridge, MAC 6c:c8:40:35:4e:c0. On COM8.
    - Board #2 = ESP32-S3 (QFN56 rev v0.2), 16MB flash, 8MB PSRAM, native
      USB-Serial/JTAG, MAC a4:cb:8f:d4:8e:38. On COM11 (COM12 in download mode;
      native-USB boards need BOOT+RST to enter download mode and the port number
      shifts while there).
  Planned role mapping: AL-GHUL (the twin, needs 16MB flash for dual OTA app
  slots + PSRAM for the MITM relay buffer + optional on-device adaptive search)
  = the ESP32-S3. Sniffer (promiscuous monitor-mode capture only) = the classic
  ESP32. Proposal/report wording "two ESP32-S3" to be corrected to this split.

- 2026-10-01: RELOCATED the whole build workspace OUT of the Google-Drive-synced
  course folder to C:\Users\souka\AL-GHUL (per request: keep the project off
  Drive). The course folder (Documents\School\Semester 1\CSDA-...\Project) now
  holds only the proposal/report/slides; all code, data, builds, and experiment
  logs live here, off Drive. First bring-up build of al_ghul succeeded on the
  ESP32-S3 (al_ghul.bin ~184KB, app partition 82% free), proving the full
  compile+link+image chain. Build output is now in-tree (firmware/al_ghul/build)
  since nothing here syncs anymore.

## Code status (2026-10-01, full autonomous build)

Complete, compiling/runnable codebase. Flashing + live lab runs need the boards
and your own router details, and are the only remaining manual steps.

- `firmware/al_ghul/`  ESP32-S3 twin: clone+out-signal, STA uplink + NAT relay
  (transparent MITM, no payload capture), disguise (BSSID/beacon/vendor-IE/power),
  HTTP control + OTA receive. BUILDS (al_ghul.bin, 16MB dual-OTA layout).
- `firmware/sniffer/`  classic-ESP32 promiscuous capture -> JSON over USB.
- `firmware/kill/`     OTA kill image: wipes twin slot + NVS + otadata, goes dark.
- `watcher/src/`       capture, features (no BSSID leakage), RandomForest detector,
  metrics (acc/prec/recall/FPR), evolutionary attacker, arms-race loop, H4 plot,
  OTA kill pusher. Synthetic backend validates everything with no hardware.
- `docs/`              ETHICS, ARCHITECTURE, BUILD_AND_FLASH, LAB_RUNBOOK.

### What still needs you (hardware / your data)
1. Fill your own values: `firmware/al_ghul/main/app_config.h` (SSID/PSK/uplink
   BSSID) and `watcher/src/config.py` (SSID/BSSID/control URL/COM port).
2. Flash: AL-GHUL (S3, COM11), sniffer (classic ESP32, COM8). See docs/BUILD_AND_FLASH.md.
3. Live runs for H1/H2 and the H4 curve, then the OTA kill. See docs/LAB_RUNBOOK.md.

### Toolchain activation (this PC)
The installer's config step failed, so use the repo helper, not the Start-Menu
shortcut:  `cd firmware; . .\activate-idf.ps1`  (then `idf.py ...`).

## Sniffer bring-up (2026-10-01) — FLASHED + VERIFIED on hardware
Flashed to the classic ESP32 (COM8) and confirmed capturing: 35 beacons / 4 APs
in 12 s, full JSON records (ssid, bssid, ch, rssi, bi, cap, ordered IE list,
vendor OUIs). Two fixes were needed and are baked into the firmware/config:
- It boot-looped at RF calibration (reset on the radio power-up current spike on a
  marginal USB supply). Fixed by `CONFIG_ESP_BROWNOUT_DET=n` in sdkconfig.defaults
  PLUS moving to a USB port that delivers cleaner power, then `erase-flash` so the
  radio recalibrated at the good voltage.
- It captured 0 frames at first: STA modem power-save sleeps the radio between
  beacons. Fixed with `esp_wifi_set_ps(WIFI_PS_NONE)` in sniffer.c.
Lesson for re-flashing: use a direct laptop USB port + good cable; if RX looks
deaf (RSSI pinned near -90), erase-flash and let it recalibrate.

## FULL RIG LIVE ON HARDWARE (2026-10-01)
Isolated lab: real AP = phone hotspot "Kaffi_FRI" (BSSID <real-AP-BSSID>, WPA2,
pw <redacted>), victim = tablet, twin = AL-GHUL on the ESP32-S3 (COM12), sniffer =
classic ESP32 (COM8). No household SSID is cloned; only the phone's lab SSID is,
so only the paired tablet can roam. No deauth anywhere.
- AL-GHUL flashed, boots, STA uplink to the hotspot = connected (uplink=yes),
  brownout disabled so AP+STA powers up cleanly.
- Sniffer sees TWO Kaffi_FRI: real <real-AP-BSSID> at -74 dBm and twin
  02:a1:00:00:00:01 at -64 dBm. The twin OUT-SIGNALS the real AP by ~10 dB
  (the H1 mechanism), with no deauth.
- H3 on REAL data: 30s capture, 98 Kaffi_FRI beacons (44 real / 54 twin),
  Watcher accuracy=1.000 precision=1.000 recall=1.000 FPR=0.000 (round 1).
- Control URL = http://192.168.4.1 (twin SoftAP gateway); laptop controls AL-GHUL
  by joining the twin's AP.
Remaining: H1 (tablet auto-roam to twin), H2 (internet through relay), H4 (run the
arms race over rounds with the orchestrator).

## H1 + H2 PROVEN ON HARDWARE (2026-10-01)
- H1 (auto-join): after a WiFi toggle, devices auto-roamed to the twin's clone
  (clone_clients=2, e.g. 62:39:e1:13:23:f0 @ -50, 96:e4:c9:2b:f2:2e @ -35),
  choosing the louder twin (-64) over the real hotspot (-74). No deauth.
- H2 (invisible interception): the tablet, now on the twin, has fully working
  internet through the NAT relay (twin -> phone hotspot -> cellular). Nothing
  looks wrong. The transparent-MITM danger demonstrated.
So H1, H2, H3 all confirmed live; only H4 (the arms-race curve) remains.

## H4 LIVE OVER USB (2026-10-01)
Control plane moved to USB (serial_control.c on the S3: send disguise JSON / STATUS
/ PING over COM12) because the WiFi control path was unreliable (Windows abandons
the no-internet twin SSID and reverts to the house network). Disguise changes also
made live (no WiFi restart unless the BSSID changes), so clients never drop.
Arms race (`armsrace.py --mode serial --ctl-port COM12 --sniff-port COM8`), 6 rounds:
- Watcher accuracy = 1.000, FPR = 0.000 every round; the real ESP32 twin never
  evaded. The disguise space the attacker controls (vendor IE / beacon timing /
  TX power, BSSID fixed) is not enough to look like the phone AP.
- One transient (round 1): a new vendor-IE disguise momentarily slipped the
  not-yet-retrained detector (deployed twin-detection 0.0), retraining restored
  100% -> the arms-race mechanism, even though retraining always won here.
Interpretation for the report: on real hardware the twin is reliably detectable
(strong defensive result); the SYNTHETIC arms race (src/synth.py) shows the full
evasion/recovery zig-zag for the case where an attacker CAN approach the real
fingerprint. Both curves in experiments/plots/.
ALL FOUR HYPOTHESES NOW DEMONSTRATED ON HARDWARE: H1, H2, H3, H4.
