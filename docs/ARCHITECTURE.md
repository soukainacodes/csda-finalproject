# Architecture

```
                 2.4 GHz beacons
  [ Real AP ] -------------------\
  (phone hotspot)                 \        USB serial (JSON captures)
       ^  (uplink STA)             v       +---------------------------+
  [ AL-GHUL  ESP32-S3 ] <~beacons~> [ the Watcher  ESP32-S3 ] ----> [ Laptop ]
   - clones SSID, out-signals        - promiscuous sniff             - logging
   - STA uplink + NAT relay (MITM)   - on-board detectors +          - offline detectors
   - disguise: bssid/beacon/IE/power   LED: rule-1 / IE-fp / TSF       (clock-skew, seq,
   - HTTP control + OTA receive                                        beacon-rate) + ML
         ^                        <-- HTTP /disguise,/status,/ota ----- control + kill push
         |                        <-- OTA kill image (optional demo) --
       2.4 GHz (same SSID+PSK: it is her own network)
  [ Her phone ] auto-joins the louder twin, keeps working internet
```

There are exactly two ESP32-S3 boards: the twin (AL-GHUL) and the Watcher. The
Watcher does both the promiscuous sniffing and the live on-board detection; the
laptop is only the logger and the offline/ML leg. The "sniffer" is the Watcher's
role, not a separate device.

## Components

| Path | Board / host | Role |
|---|---|---|
| `firmware/al_ghul/` | ESP32-S3 (16MB) | the twin: clone + out-signal + NAT relay + control + OTA |
| `firmware/sniffer/` | ESP32-S3 | the Watcher: promiscuous sniff + on-board detectors (rule-1 / IE-fingerprint / TSF) + LED, streams JSON to the laptop |
| `firmware/kill/`    | ESP32-S3 (OTA image) | wipes the twin's flash; the finisher (optional lab-only demo) |
| `firmware/pwned/`   | ESP32-S3 (OTA image) | the "owned" takeover banner image (optional lab-only demo) |
| `watcher/src/`      | laptop (Python) | logging, offline detectors + classifier, arms-race framework, plots, kill push |

## Disguise knobs (the attacker's genome)

`ap_bssid` (incl. locally-administered bit), `beacon_interval`, `tx_power`
(out-signal level), and an optional `vendor_ie` (OUI + payload). These are exactly
the fields the Watcher fingerprints, so they are the axes of the arms race.

## Watcher features (no BSSID identity, to avoid label leakage)

beacon interval; beacon-timing mean/jitter (per BSSID); RSSI mean/std; IE count;
one-hot of common IE tag ids; vendor-IE count; capability bits; locally-
administered MAC bit.

## Control protocol (laptop -> AL-GHUL, HTTP on port 80)

- `GET /status` -> chip/heap/uplink/running-partition/current disguise (JSON)
- `POST /disguise` -> JSON patch `{bssid,beacon_interval,tx_power,vendor_ie}`;
  applied ~0.5 s after the reply (so the reply is delivered before WiFi restarts)
- `POST /ota` -> raw firmware image -> inactive OTA slot -> reboot (normal update
  or the kill image)

## Partition layout (AL-GHUL, 16MB)

`nvs(24K) + otadata(8K) + phy(4K) + ota_0(4M) + ota_1(4M)`. Two equal app slots so
the kill image lands in the inactive slot and boots from there.

## Hypotheses -> where they are produced

- **H1 trust** (phone auto-joins louder twin): clone SSID+PSK + max tx power +
  placement. Measured by observing the phone's association.
- **H2 invisibility** (internet still works): the NAT relay (`napt_relay.c`).
- **H3 detectability** (catches the exact-BSSID clone): the on-board detectors in
  `firmware/sniffer/main/detector.c` (live, the primary defender), plus the offline
  detectors and classifier (`train.py` + `evaluate.py`). This is the project's result.
- **H4 arms race** (framework, demoted to a limitation): `armsrace.py` + `plot_curve.py`;
  on real hardware the attacker never evaded, so it is reported as a limitation, not a result.
