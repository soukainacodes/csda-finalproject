# Architecture

```
                 2.4 GHz beacons
  [ Real router ] ----------------\
       ^  (uplink STA)             \         USB serial (JSON records)
       |                            v       +--------------------------+
  [ AL-GHUL  ESP32-S3 ]  <~~beacons~~>  [ Sniffer ESP32 ] ---------> [ Laptop: Watcher ]
   - clones SSID, out-signals        (promiscuous, RX only)          - features + ML
   - STA uplink + NAT relay (MITM)                                    - metrics (acc/FPR)
   - disguise: bssid/beacon/IE/power                                  - arms-race loop
   - HTTP control + OTA receive  <----- HTTP /disguise, /status, /ota ---- attacker AI
                                  <----- OTA kill image (finisher) ------- kill-switch
       ^
       | 2.4 GHz (same SSID+PSK: it is her own network)
  [ Her phone ] auto-joins the louder twin, keeps working internet
```

## Components

| Path | Board / host | Role |
|---|---|---|
| `firmware/al_ghul/` | ESP32-S3 (16MB) | the twin: clone + out-signal + NAT relay + control + OTA |
| `firmware/sniffer/` | classic ESP32 (4MB) | promiscuous beacon/probe capture, JSON over USB |
| `firmware/kill/`    | ESP32-S3 (OTA image) | wipes the twin's flash; the finisher |
| `watcher/src/`      | laptop (Python) | capture, features, classifier, arms race, plots, kill push |

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
- **H3 detectability** (accuracy A, FPR F): Watcher `train.py` + `evaluate.py`.
- **H4 arms race** (curve over rounds): `armsrace.py` + `plot_curve.py`.
