# Scope and ethics

This project is a self-contained, measured security experiment for the CSDA final
project (T-742-CSDA, RU, Jacky Mallett). The research contribution is the
**defender**: a machine-learning detector (the Watcher) and the measured
attacker-vs-defender arms-race curve. The attacker (AL-GHUL) exists only to
produce a controllable adversary to train and score the detector.

## Hard rules (enforced in design, not just stated)

- **Own equipment only.** Everything runs on the student's own ESP32-S3, own
  classic ESP32, own home router, own phone, and own laptop, on an isolated home
  lab network. Never on production, never on work (Stokkseyri) WiFi, never on any
  network or device not owned by the student.
- **Out-signal, never hide.** The twin only broadcasts a (louder) beacon and
  relays traffic. There is **no deauthentication and no jamming** anywhere in the
  codebase. The firmware has no code path that transmits deauth/disassoc frames
  or otherwise forces any device off any network. Grep the firmware: there is no
  `deauth`, no raw-frame injection for disruption.
- **Only the student's own phone** is ever a client of the twin. No third-party
  traffic is involved.
- **No payload interception.** The transparent relay is an ordinary NAT repeater.
  AL-GHUL does **not** capture, log, decode, or modify client payloads. H2 only
  requires that the internet keeps working through the relay, which is what makes
  the interception "invisible"; it does not require reading the victim's data, and
  the code does not.
- **The kill-switch is a command to an owned device.** It is an authenticated-by-
  design OTA update the board was built to accept. It is not a break-in and not an
  exploit of anyone else's device, and it uses no deauth and no jamming.

## Why the attacker half is necessary and appropriate

You cannot measure a detector without something to detect. Building a controllable
twin in an isolated lab, on owned hardware, with no disruptive techniques, is the
standard shape of responsible security research and of any supervised
penetration-testing exercise: controlled environment, owned equipment, no
collateral damage.
