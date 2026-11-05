# Build and flash

ESP-IDF v5.2.8 is installed at `C:\Espressif`. The installer's final config step
failed on this PC, so **do not** use the Start-Menu "ESP-IDF PowerShell"; instead
activate the environment with the helper in this repo.

## 1. Activate ESP-IDF (every new terminal)

```powershell
cd C:\Users\souka\AL-GHUL\firmware
. .\activate-idf.ps1          # note the leading dot (dot-source)
idf.py --version              # should print ESP-IDF v5.2.8
```

## 2. Fill in your own values first

- `firmware/al_ghul/main/app_config.h`: `ALGHUL_TARGET_SSID`, `ALGHUL_TARGET_PSK`,
  and `ALGHUL_UPLINK_BSSID` (your real router's BSSID; find it with
  `netsh wlan show interfaces`).
- `watcher/src/config.py`: `REAL_ROUTER_SSID`, `REAL_ROUTER_BSSID`,
  `ALGHUL_CONTROL_URL`, `SNIFFER_SERIAL_PORT`.

## 3. Build + flash AL-GHUL (ESP32-S3)

Target is already set to esp32s3. Plug in the S3 (shows as COM11; in download
mode it may shift to COM12).

```powershell
cd C:\Users\souka\AL-GHUL\firmware\al_ghul
idf.py build
idf.py -p COM11 flash monitor
```

If flashing cannot connect ("No serial data received"): hold **BOOT**, tap
**RST**, release **BOOT**, then re-run. Exit the monitor with `Ctrl+]`.

## 4. Build + flash the Watcher (ESP32-S3)

The Watcher is the second ESP32-S3 (same chip as the twin); its target is
**esp32s3**. Plug in the Watcher S3 (shows as COM15; the twin is COM18).

```powershell
cd C:\Users\souka\AL-GHUL\firmware\sniffer
idf.py set-target esp32s3
idf.py build
idf.py -p COM15 flash monitor
```

You should see one JSON line per beacon. By default it hops channels 1..13; to
lock to your router's channel, build with
`idf.py -DSNIFFER_LOCK_CHANNEL=<ch> build` or set it in `sdkconfig`.

## 5. Build the kill image (ESP32-S3): do NOT flash it

The kill image is delivered to AL-GHUL over OTA, not flashed over USB.

```powershell
cd C:\Users\souka\AL-GHUL\firmware\kill
idf.py set-target esp32s3
idf.py build
# produces build/kill.bin -> pushed later by watcher/src/killswitch.py
```

## Notes

- All build output stays under `C:\Users\souka\AL-GHUL` (off Google Drive).
- Both boards are ESP32-S3 with the console on native USB-Serial/JTAG (twin COM18,
  Watcher COM15). Open these ports with dtr=False, rts=False so a connect does not
  reset the board.
