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

## 3. The Watcher (detection): how H3 works

The Watcher is the second ESP32-S3. In **promiscuous mode** it copies every
beacon/probe off the air and, on the board itself, runs the primary detectors live:
rule-1 (how many BSSIDs advertise one SSID), an information-element fingerprint, and a
TSF clock check, lighting its LED on detection. These device-independent tells catch
even a twin that clones the real BSSID exactly, which the count rule alone misses. The
board also streams one JSON record per frame to the laptop, where further detectors run
offline (clock-skew fit, sequence-number, beacon-rate) alongside a RandomForest that
turns those records into features and classifies each frame as **real** or **twin**.

**Key design rule:** we *label* frames by BSSID (real AP vs anything else on the
same SSID), so we must **never use the BSSID as a feature**, that would be
label leakage. The detector only sees radio/behavioural fingerprints:

- beacon interval, and beacon-timing jitter (an ESP32's clock wobbles differently)
- RSSI mean/variation
- which information elements are present, and how many
- vendor-specific IEs
- capability bits
- the locally-administered MAC bit (an evadable tell)

A `RandomForest` trained on the **real** captures (no synthetic data, no BSSID/MAC as a
feature) separates twin from real with zero false positives, **but with two radios that is
separability, not generalization**. Its real value is that its feature importances
independently rank the same physical tells the hand detectors use (clock-skew, IE, timing).
Honest write-up: [`experiments/ml-real-results.md`](../experiments/ml-real-results.md). An
earlier synthetic model reported a perfect score, but that was circular (the gap was hand-coded
into the generator); see [`experiments/ml-watcher-limitations.md`](../experiments/ml-watcher-limitations.md).

Code: `watcher/src/features.py` (features), `watcher/src/train.py` (classifier),
`watcher/src/evaluate.py` (metrics).

## 4. The arms race: how H4 and the fighting graph work

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

**Honest result:** this is a **framework, not a result.** The "clean zig-zag" only appears in
the **synthetic** run (`--mode synth`), where the gap was hand-coded into the generator, so its
perfect accuracy is circular. On **real hardware** the curve stayed **flat** (the ESP32's
disguise knobs are too coarse to evade), which we report as a **limitation**, not a strong
defensive result. The project's own [`ml-watcher-limitations.md`](../experiments/ml-watcher-limitations.md)
demolishes the earlier 100% claim; the detection findings rest on the measured physical detectors.

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
*(The values in `app_config.h` are **lab throwaways**; replace them with your own before you run this, and do not reuse them anywhere real.)*

## 5.5 From kill to takeover, and why it matters

> This section and 5.6 are an optional, lab-only demonstration. They are not the
> project's result (which is the on-board detection in section 3) and they work only
> because the board is owned and ships with every hardware protection off. Reported
> as a demo, not a headline.

Wiping the board is the *polite* use of its weakness. The same defaults-off state
means a compromised ESP32 can be **taken over**, not just switched off:

- **Remote reflash (OTA takeover):** with the control channel reachable and the
  secret known (and we just showed the secret is dumpable), new firmware can be
  pushed over the air, the board now runs the operator's code.
- **Credential-less crash:** the ESP WiFi stack has a documented class of bugs
  where a single crafted 802.11 frame from radio range crashes it, no password
  needed (CVE-2019-12586 / CVE-2019-12588).
- **Clone:** the plaintext flash dump is enough to rebuild an identical board.

On our own board this is the tame version (own channel, known secret). The point
is the **class**: in the wild this has been fully unauthenticated, remote code
execution over the air with no pairing at all (BrakTooth, CVE-2021-28139). A
microcontroller cannot defend itself; the defence is the environment around it.
The real incidents and CVEs behind each of these, with citations, are collected
in [MCU_SECURITY.md](MCU_SECURITY.md), which is the evidence for this project's
thesis: **small embedded chips must be deployed in protected environments, with
their security features (flash encryption, secure boot, signed OTA) switched on.**

## 5.6 The autonomous kill (the Watcher closes the loop)

The finisher does not need a human. `watcher/src/sentinel.py` is the Watcher
running as a closed loop: it watches the sniffer stream, scores every BSSID on
the target SSID with the trained detector, and the moment a non-real BSSID is
confidently a twin (>=80% of its frames, sustained over two windows) it fires the
response by itself. It timestamps every step, so each run yields real numbers:

- **time-to-detect**: from the twin appearing on the air to the Watcher being sure
- **time-to-neutralise**: from sure to the board being dead
- **total**: appear to dead

These land in `experiments/round-logs/neutralize-*.json` and as a timeline figure
in `experiments/plots/`. In the synthetic dry-run the whole thing takes well under
a second; on hardware the OTA push dominates.

The response escalates through three visible, real stages:

1. **Takeover (OTA).** The Watcher reflashes the twin with `firmware/pwned` over
   its own OTA channel. That image is deliberately, visibly not the twin any more:
   its SoftAP announces `NEUTRALIZED_BY_THE_WATCHER` and the onboard LED glows red.
   It proves that with flash encryption and secure boot off (the ESP32 default),
   whoever holds the OTA channel owns the device.
2. **The death rattle.** The kill path flips AL-GHUL's SoftAP to `AL-GHUL_DOWN`
   before wiping, so the sniffer and every phone *see* the twin die, then it erases
   its flash and goes dark.
3. **The post-mortem.** `watcher/src/forensics.py` dumps the dead board and reads
   its diary: the recovered secrets (cleartext, because encryption is off) and the
   list of every MAC that joined the clone, which the twin logs to NVS as clients
   connect (metadata only, never payloads).

During a live talk the whole sequence is mirrored onto the audience companion:
`ALIVE` flips to `TARGET DOWN` with the latency numbers, pushed from the sentinel.
The point of making it autonomous and measured: an AI that finds a rogue AP and
ends it on its own is exactly why these devices must sit in protected environments.

## 6. The honest limit

You cannot remotely kill a **stranger's** rogue AP: you wouldn't have its token,
its password, or its update channel, and unauthorized remote wiping is illegal.
The kill-switch works here only because the board is the author's own. Against a
real adversary the deployable defence is **detection (the Watcher) + WPA3/PMF +
locate-and-remove**, not counter-hacking. Stating that limit is part of the result.
