# How it works

A plain-language walkthrough of the detection, the arms race, and the finisher.
For the data flow and partition layout see [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. The weakness being exploited

A phone picks a WiFi network by its **name (SSID)**, which is not unique and not
verified: beacons and probe responses are unauthenticated. On **WPA2**, any AP
that broadcasts the right name *and* knows the password is indistinguishable from
the real one, the protocol only proves knowledge of the password, never the AP's
identity. So a twin that clones your own network (whose password you know) is
accepted seamlessly. **WPA3 + Protected Management Frames is the fix**, which is
exactly why the attack is demonstrated on WPA2.

## 2. The twin (AL-GHUL)

An ESP32-S3 brings up a SoftAP with the **same SSID and password** as the real
AP and turns its transmit power up, so it **out-signals** the real one and devices
roam to it on their own. It also runs as a **transparent NAT relay**: it carries
the victim's traffic out through its own uplink, so the internet keeps working.
It never deauthenticates or jams anything, and it never inspects payloads. Its
disguise (BSSID, beacon interval, vendor IE, TX power) can be changed live.

## 3. The Watcher (detection) — how H3 works

A second ESP32 in **promiscuous mode** copies every beacon/probe off the air and
streams one JSON record per frame to the laptop. The Watcher turns those into
features and classifies each as **real** or **twin**.

**Key design rule:** we *label* frames by BSSID (real AP vs anything else on the
same SSID), so we must **never use the BSSID as a feature**, that would be
label leakage. The detector only sees radio/behavioural fingerprints:

- beacon interval, and beacon-timing jitter (an ESP32's clock wobbles differently)
- RSSI mean/variation
- which information elements are present, and how many
- vendor-specific IEs
- capability bits
- the locally-administered MAC bit (an evadable tell)

A `RandomForest` classifier learns these. On live captured beacons it reached
**accuracy 1.00, precision 1.00, recall 1.00, false-positive rate 0.00** (the
false-positive rate matters: a detector that cries wolf on real APs is useless).

Code: `watcher/src/features.py` (features), `watcher/src/train.py` (classifier),
`watcher/src/evaluate.py` (metrics).

## 4. The arms race — how H4 and the fighting graph work

The attacker is an **evolutionary search** (`watcher/src/attacker.py`): each round
it tries a few random tweaks to its disguise, reads how well the current detector
catches it, and keeps the most evasive variant. The loop
(`watcher/src/armsrace.py`) measures two things each round:

1. **Deployed detector vs the NEW disguise** (before retraining). This is the
   realistic case: a fielded detector meeting an attack it never trained on. When
   the attacker finds a novel trick this **dips**.
2. **Accuracy after retraining** on the new disguise. The Watcher **recovers**.

Plotting those across rounds is the fighting graph
([`experiments/plots/fighting-graph.png`](../experiments/plots/fighting-graph.png)):
the black line dips when the attacker evades, the gold line climbs back after the
Watcher retrains.

```
for r in range(rounds):
    attacker.adapt(...)                      # evolve vs the DEPLOYED detector
    recs = backend.capture()                 # sniff this round's beacons
    dep_acc = accuracy(deployed_model, recs) # EVASION  -> the dips
    model   = retrain(all_records_so_far)    # RECOVERY -> back to ~100%
    deployed_model = model                   # this round's model is next round's "deployed"
```

**Honest result:** the clean zig-zag is the **synthetic** run (`--mode synth`),
where the attacker can approach the real fingerprint. On **real hardware** the
ESP32 twin differs from a phone AP in too many stable ways to ever evade, so the
live curve stayed **flat at 100%**, a strong defensive result. Both are reported.

## 5. The finisher (kill-switch), and why it is weak

When the Watcher is confident, the operator sends an **authenticated** command
(`/kill?token=...`, or over USB) to AL-GHUL's own control channel; the board
erases its flash and goes dark. It is a kill-switch on an **owned** board, built
to obey the command, not a break-in, and it uses no deauth.

**The twist (a real, recurring MCU weakness):** the ESP32 ships with **flash
encryption off** by default. A single standard command, `esptool read_flash`,
dumps the flash, and the kill **token** and the **WiFi password** are sitting in
it in **plaintext**. So the "authentication" is only as strong as the chip's
secret storage, which by default is an open book. This mirrors hardcoded-secret
failures in the wild (OWASP IoT #1; Mirai) and routine MCU flash extraction.
**Mitigation:** enable flash encryption + secure boot, and never hardcode secrets.
*(That is why nothing in this repo hardcodes a secret, see `app_config.h`.)*

## 6. The honest limit

You cannot remotely kill a **stranger's** rogue AP: you wouldn't have its token,
its password, or its update channel, and unauthorized remote wiping is illegal.
The kill-switch works here only because the board is the author's own. Against a
real adversary the deployable defence is **detection (the Watcher) + WPA3/PMF +
locate-and-remove**, not counter-hacking. Stating that limit is part of the result.
