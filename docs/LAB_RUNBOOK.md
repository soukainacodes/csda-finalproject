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

1. Power the sniffer (ESP32-S3, COM14 - was the classic ESP32 on COM8). Confirm it
   streams beacons:
   `python -c "from src.capture import stream; [print(r) for r in stream('COM14',115200)]"`
   (Ctrl+C to stop.) Set the port in `config.SNIFFER_SERIAL_PORT` if yours differs.
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

## C. The finisher: from kill to takeover

Prerequisite: set `config.ALGHUL_CONTROL_TOKEN` to the same secret as
`app_config.h` (for the real lab, `ghoul-begone-2026`), and join the laptop to the
twin's own AP so `http://192.168.4.1` reaches it.

`src.takeover` runs an escalation ladder; each level runs the ones below it first.

```powershell
# 1) REACH - prove the Watcher can talk to the twin (read-only)
python -m src.takeover --level reach

# 2) PROVE - command it live: flip its beacon_interval, watch the sniffer see it change
python -m src.takeover --level prove

# 3) OWN - reflash it over the air with firmware WE choose (OTA takeover)
python -m src.takeover --level own --image ..\firmware\al_ghul\build\al_ghul.bin --yes

# 4) KILL - make it erase itself and go dark
python -m src.takeover --level kill --yes
```

Level `own` is an optional lab-only "remote takeover" demo: the board ends up running an image
the operator pushed. Level `kill` is the clean finish (same effect as the older
`python -m src.killswitch --image ..\firmware\kill\build\kill.bin --yes`, which
still works and now sends the token too). After a kill, only a physical USB
re-flash revives the board (BUILD_AND_FLASH.md step 3).

Honest framing: this works because it is **your own** board and you hold its
token (and, as section D shows, on an unprotected board the token is dumpable
anyway). Against a stranger's rogue AP you would not have the token, the channel,
or the legal right, the deployable defence is the Watcher + WPA3/PMF + locate-
and-remove (see docs/HOW_IT_WORKS.md section 6).

## C.2 The credential-less crash (real-world class, no secret at all)

The third real attack class needs **no token**: a single crafted 802.11 frame from
radio range crashes the ESP WiFi stack (CVE-2019-12586 / CVE-2019-12588; see
docs/MCU_SECURITY.md). This is run from a monitor-mode injector, not the control
channel, and only against your own twin:

```bash
# Linux box with a monitor-mode NIC, e.g. in the lab. Example shape only:
#   sudo airmon-ng start wlan0
#   sudo python3 crash_frame.py --iface wlan0mon --target <AL-GHUL BSSID>
# where crash_frame.py sends a malformed RSN-IE beacon/assoc-resp per the CVE.
```

Record whether AL-GHUL reboots (watchdog recovers) or deadlocks (no auto-reboot),
that difference is itself the finding about why robustness + auto-reboot matter.
Note: our twin is an AP, so reproducing the exact CVE path may need the right
frame type/state; capture the serial log either way as evidence.

## D. Flash-dump evidence (the twist)

With AL-GHUL on USB, dump its flash and show the secrets are plaintext:

```powershell
esptool.py --port COM11 read_flash 0x0 0x400000 alghul_flash.bin
# then search the dump for the SSID, the WiFi password, and the control token
python -c "d=open('alghul_flash.bin','rb').read(); import re; print([s.decode(errors='replace') for s in re.findall(rb'[ -~]{6,}', d) if b'ghoul' in s or b'coffee' in s.lower()])"
```

Finding both the WiFi password and the kill token in cleartext is the proof that
"authenticated" is only as strong as the chip's (default-off) secret storage.
Mitigation: enable flash encryption + secure boot (docs/MCU_SECURITY.md).

## E. The autonomous kill (optional lab-only demo)

The Watcher does not wait for a human. `src.sentinel` watches the air, and the
moment it is confident a twin is present it runs the takeover/kill chain by
itself, timestamping every step so you get real numbers.

```powershell
# dry-run, no hardware: watch it detect + "neutralise" a synthetic twin and
# produce the latency figure for the report (experiments/plots/neutralize-*.png)
python -m src.sentinel --mode synth

# LIVE and armed: real sniffer, real neutralisation over AL-GHUL's control plane.
# Pushes the "owned" payload first (SoftAP -> NEUTRALIZED_BY_THE_WATCHER, red LED),
# then the kill. Mirrors TARGET DOWN + the latency onto every audience phone.
python -m src.sentinel --mode serial --arm `
  --own-image ..\firmware\pwned\build\pwned.bin `
  --token ghoul-begone-2026 `
  --companion-url https://ghoul.lausnanet.is --companion-key <PRESENTER_KEY>
```

What it writes each run (under `experiments/`):
- `round-logs/killcam-<ts>.jsonl` - every event with a monotonic timestamp
- `round-logs/neutralize-<ts>.json` - detect / neutralize / total latency
- `plots/neutralize-<ts>.png` - the timeline figure

The two visible payloads (build once, flashed/pushed later):
- `firmware/pwned/build/pwned.bin` - the "owned" takeover image (SSID rename + red
  LED). The Watcher pushes it over OTA to prove it controls the attacker's board.
- AL-GHUL's own kill path now does a **death rattle**: it flips its SoftAP to
  `AL-GHUL_DOWN` so the sniffer and phones see the twin die, then wipes.

## F. Post-mortem forensics (read its diary)

After the kill, dump the dead board and recover its secrets and its victim log:

```powershell
# analyse a dump you already pulled
python -m src.forensics --dump ..\experiments\alghul_flash.bin
# or pull it first from an ESP-IDF shell (esptool on PATH)
python -m src.forensics --read --port COM11
```

Recovers (all cleartext, because flash encryption is off): the cloned SSID, the
WiFi password, the control/kill token, the saved disguise, and the **victim
diary** (every MAC that joined the clone, which AL-GHUL now logs to NVS as clients
connect, metadata only, never payloads). Report lands at
`experiments/forensics-report.md`.

## What to collect for the report (the 50%)

The result, collect these first:
- The on-board detector comparison across A/B/C (`experiments/master-detector-comparison.md`
  + `experiments/onboard-results-2026-11-05.md`): which detector catches the exact-BSSID
  clone, and the detection-latency distribution (median 3 s, range 2 to 10 s, n=9). This is H3.
- The security-mode matrix (`experiments/security-mode-matrix.md`): which modes still allow
  the silent capture (WPA2 / PMF / transition yes, WPA3 forces a prompt). This is H5.
- The protected-environment measurements (`experiments/protected-env/`): the eFuse states and
  the flash dump recovering the plaintext secrets, tied to the real CVEs/incidents in
  docs/MCU_SECURITY.md. This is the MCU-weakness evidence.
- Notes/screenshots for H1 (phone auto-join) and H2 (working internet).

Framework and optional lab-only demos (report as such, not as the result):
- The arms-race curve PNG + per-round CSV/JSON as the H4 framework; on real hardware it did
  not evade, so report it as a limitation.
- The takeover transcript (`src.takeover`), the autonomous-kill latency JSON + kill-cam
  (`src.sentinel`), the forensics report, and a photo of the "owned" payload: optional
  lab-only demos that work only because the board is owned and unprotected.
- If attempted, the credential-less crash serial log (reboot vs deadlock).
