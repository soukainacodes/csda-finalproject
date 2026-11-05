# Security-mode matrix: which WiFi modes still join the twin

Experiment (2026-11-04). One ESP32-S3 twin firmware, auth mode switchable live over
USB serial (`AUTHMODE OPEN|WPA2|WPA2-PMF|WPA3|WPA2WPA3`). For each mode the twin
re-advertises the clone and we measure whether the victim (Samsung tablet, Android 16)
still associates. Measurement = the twin's own heartbeat (`clone_clients` and
`security=`), the join log line, and the status LED (green empty, red joined). All on my
own devices and my own network, no deauth.

The point it tests: a "personal" mode authenticates knowledge of the PASSWORD, never the
IDENTITY of the access point. So a twin that knows the key (my own network) should be
joinable under every personal mode. Only AP-identity authentication (Enterprise with a
validated server certificate) should refuse it.

## Results

| # | Twin advertised | Victim joined? | Raw evidence |
|---|---|---|---|
| 0 | Open | (to run) | |
| 1 | WPA2-PSK | yes (baseline) | the main project runs |
| 2 | WPA2-PSK + PMF required | **YES** | clone_clients=1 under WPA2-PSK+PMF; joined 96:e4:c9:2b:f2:2e rssi -32 (see serial-console log) |
| 3 | **WPA3-SAE** | **YES** | clone_clients=1 under WPA3-SAE; joined 82:0b:90:62:d6:dc rssi -13 (see serial-console log) |
| 4 | WPA2/WPA3 transition | **YES** | clone_clients=1; tablet rejoined automatically (96:e4:c9:2b:f2:2e rssi -31). Transition always exposes the WPA2 path, the Dragonblood downgrade |

Raw evidence for cases 2 and 3: `evidence/serial-console-2026-11-04.log` (the twin's own
heartbeat, captured live over USB). Case 2 note: PMF was required and the tablet still
associated, because PMF protects management frames (it stops forged deauth), it does not
authenticate the access point. Android re-randomised its MAC between cases (82:0b.. then
96:e4..), expected per-network MAC randomisation.
| 5 | real AP WPA3-only, twin WPA2 | (needs real AP in WPA3-only) | expect refuse |
| 6 | Enterprise, no valid cert | (analysis / hostapd-wpe) | expect refuse: identity auth |

## Finding so far (case 3, the headline)

Under WPA3-SAE the tablet associated to the twin with no warning, because SAE proves the
twin knows the shared password, which it does (it is my own network's key), and WPA3
Personal has no access-point identity for the client to check. WPA3 did not stop the evil
twin here. Its real evil-twin value is elsewhere: it mandates Protected Management Frames
(stops deauth forcing) and makes the password uncrackable offline (so an OUTSIDER who does
not know the key cannot build the twin in the first place). Against an attacker who knows
the key, only certificate-based identity (Enterprise, strict server-cert validation) closes
the door.

## CORRECTED EXPERIMENT: silent auto-join from stored credentials

The runs above were MANUAL joins (forget + retype the password), which is not the real
attack. The real attack is hands-free: the phone already has the network saved and joins
the twin on its own, from the stored password, with the user typing nothing. This is H1.
Both the real AP (S24 hotspot, fully configurable) and the twin are set to the same mode.

Key mechanism we measured: a louder twin appearing next to the victim does NOT trigger a
roam, Android is sticky and clings to the real AP while it can still hear it (clone_clients
stayed 0 the whole time a matched twin sat beside the tablet). The silent capture happens
when the victim LOSES the real network (walks out of range). We simulate that by switching
the real S24 off.

| Mode (real = twin) | Silent auto-join when real AP lost? | Evidence |
|---|---|---|
| WPA2 | **YES, ~3 s, no password** | clone_clients 0 to 1 within ~3 s of S24 off; joined 96:e4:c9:2b:f2:2e rssi -41 |
| WPA2 + PMF | **YES, ~8 s, no password** | clone_clients 0 to 1 under WPA2-PSK+PMF; joined 96:e4:c9:2b:f2:2e rssi -52. PMF did not stop it |
| WPA2/WPA3 transition | **YES, ~5 s, no password** | clone_clients 0 to 1 under WPA2/WPA3-transition; joined 96:e4:c9:2b:f2:2e rssi -53 |
| WPA3-SAE | **NO, required a password** | clone_clients stayed 0 for 30 s; user observed the tablet PROMPTED for the password when connecting to the twin (real S24 off). The silent stored-credential capture FAILED under WPA3. |
| Open / Enhanced Open | (optional) | |

### The decisive finding (WPA3)

Under WPA2, WPA2+PMF and WPA2/WPA3-transition, the tablet fell onto the password-knowing
twin silently, in 5 to 11 seconds, with no typing. Under WPA3-SAE it did not: the twin stayed
empty, and the tablet demanded the Wi-Fi password when it tried to connect with the real AP off.

So the precise result is: WPA3 does not stop a MANUAL join to a known-password twin (the user
can type the password and connect, observed earlier), but it DOES break the SILENT, hands-free,
stored-credential capture, which is the actual evil-twin attack. A real victim walks by typing
nothing; on WPA2 they are taken silently, on WPA3 they would be stopped by a password prompt
they never expected. True WPA3 (not transition) is the mode that breaks the silent roam.

Honest caveat: this is the behavioural result (observed, reproducible: silent on WPA2 family,
password-prompt on WPA3). The exact SAE-level reason the phone refuses the silent re-auth would
need a packet capture to pin down, noted as future work.

### The part that matters most: WPA3 adds friction, not immunity

The silent auto-join is only the CLEANEST version of the attack, it is not what the attack
depends on. The cafe password is not a secret, it is posted on the wall and shared with every
customer, so the twin knows it too. When WPA3 refuses the silent re-join and asks for the
password, a real victim does not think "this is fake", they think "it wants the Wi-Fi password
again, I know it", and they type the known password straight into the evil twin. They land on
the attacker having actively helped, unable to tell it from the real AP. WPA3 cost the attacker
ONE extra tap.

So the corrected conclusion:
- WPA2 / WPA2+PMF / transition: silent capture, zero interaction.
- WPA3: no silent capture, but the victim re-enters the known password and is captured anyway.
  WPA3 buys friction and a weak "did the network change?" cue, not protection.
- The real weakness is the SHARED PASSWORD. Personal modes (WPA2 and WPA3) only prove knowledge
  of the password, and in a cafe everyone, the attacker included, knows it. The only control that
  actually stops the twin is IDENTITY authentication (WPA2/3-Enterprise with validated server
  certificates), where the client verifies the AP is the genuine one, not merely that it knows
  the word on the wall.

Raw: `evidence/serial-console-2026-11-04.log` (section "MATCHED CASE 1 (real S24 OFF)").

## How it was produced

`firmware/al_ghul` with the auth-mode switch (wifi_twin.c `wifi_twin_set_authmode`,
serial command in serial_control.c). Switch sent from the laptop over the board's native
USB-Serial-JTAG port; the same port streams the heartbeat that is the evidence above.
