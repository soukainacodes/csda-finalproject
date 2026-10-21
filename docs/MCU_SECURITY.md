# Why microcontrollers belong in protected environments

The demos in this project (plaintext flash dump, device cloning, the leaked kill
token) are not a one-off stunt. They reproduce a *class* of weakness that has hit
the ESP32 and comparable microcontrollers repeatedly, in the wild, with assigned
CVEs and real-world impact. This file collects that evidence so the project's
central claim, **small embedded chips must be deployed in protected environments
and with their security features enabled**, rests on documented incidents, not
assertion.

All CVEs below are real and dated. Sources are linked at the end.

## 1. Secret extraction and secure-boot bypass (physical / debug access)

This is the class our **flash-dump + clone** demo sits in.

- **CVE-2019-15894 — Secure Boot bypass via fault injection.** Physically
  glitching the ESP32 CPU at boot can skip the Secure Boot digest check and run
  unverified code from flash. With flash encryption off, that is arbitrary code
  execution. Found by Riscure and independently by LimitedResults.
- **CVE-2019-17391 — eFuse read-protection bypass.** Fault injection right after
  reset can corrupt the eFuse read-out and recover the **flash-encryption and
  secure-boot keys** stored in eFuse. Once you have the flash-encryption key, the
  entire flash (firmware + secrets) is readable. Later silicon (ESP32-D0WD-V3)
  added ROM checks that block this specific attack, newer research (Raelize,
  "Breaking the ESP32 V3") kept finding glitch paths.
- **CVE-2025-27840 — 29 undocumented HCI commands (Tarlogic, March 2025).** The
  ESP32 Bluetooth controller hides vendor commands including memory read/write
  (0xFC02), MAC spoofing and packet injection. Widely mis-reported as a
  "backdoor", then downgraded: it is **not remotely exploitable**, needs wired
  HCI access and controller privileges, i.e. a post-exploitation / supply-chain
  tool, not instant game-over. Included here precisely because the honest reading
  matters: undocumented memory-write primitives in a billion-device chip.

**What it proves for us:** a few seconds of physical or debug access to an
unprotected ESP32 yields its firmware and every secret in it. Our plaintext
`esptool read_flash` is the easy end of this same spectrum.

## 2. Over-the-air crash / denial of service (no credentials)

This is the class our **credential-less crash** angle sits in: an attacker in
radio range, with no password and no pairing, knocks the chip over.

- **CVE-2019-12586 / CVE-2019-12588 — crafted 802.11 frames crash the WiFi stack.**
  The ESP32/ESP8266 802.11 MAC does not validate the RSN AuthKey-suite / cipher
  counts in beacons, probe responses and association responses; a crafted frame
  from radio range crashes the device. **This is the WiFi equivalent of our twin's
  weakness, and the most directly relevant: our twin is a WiFi AP.**
- **CVE-2026-17054 — malformed control frame, ~62 KB buffer over-read** in the
  ESP-hosted WiFi driver (Zephyr), DoS by crashing the WiFi stack until reboot.
- **SweynTooth (2020), CVE-2020-13594 / CVE-2020-13595** — on the BLE side: an
  invalid channel-map connection request crashes the ESP32 BLE controller, and an
  MIC-failure sequence silently disables its BLE stack via a reachable assertion.
  Attacker in radio range, no authentication. If the firmware does not auto-reboot,
  the crash becomes a deadlock requiring a manual power cycle.

**What it proves for us:** these chips have so little margin that a single
malformed frame from across the room reboots or deadlocks them. An MCU cannot
defend itself; it relies entirely on its environment.

## 3. Over-the-air remote code execution (no authentication)

The strongest evidence that "take over the chip remotely" is real, not theory.

- **BrakTooth (2021), CVE-2021-28139 — remote code execution on the ESP32 over
  Bluetooth, with no pairing.** The Bluetooth-Classic LMP implementation in
  ESP-IDF 4.4 and earlier mishandles a crafted LMP Feature Response Extended
  packet, allowing an attacker in radio range to execute arbitrary code. Part of a
  16-bug family that the researchers estimated could affect ~1,400 products reusing
  the same stack.

**What it proves for us:** a real, assigned CVE where someone in radio range took
*full control* of an ESP32 with no credentials at all. Our remote-OTA takeover
(using a leaked secret) is the tame, polite version of a danger that has existed
unauthenticated in the wild.

## 4. Unprotected embedded devices at scale

- **Mirai (October 2016).** Malware that logged into IoT devices (DVRs, IP cameras,
  routers) using a list of ~62 default/**hardcoded** credentials over Telnet/SSH,
  built a botnet of an estimated ~150,000 devices, and took down DNS provider Dyn
  at a peak of ~1.2 Tbps, knocking out Twitter, Netflix, Reddit, GitHub, Spotify
  and more. Many devices could not be fixed because the password was hardcoded in
  firmware.

**What it proves for us:** hardcoded secrets in embedded devices (the exact thing
our flash dump exploited) have already caused one of the largest DDoS events in
history. One hardcoded secret, multiplied across a fleet, is a systemic failure.

## How this maps to the project

| Project demo | Real-world class | Representative CVE / event |
|---|---|---|
| Plaintext flash dump → recover token + PSK | secret extraction, no flash encryption | CVE-2019-17391, Mirai (hardcoded secrets) |
| Clone the board from its dump | firmware/identity not protected | (same; secure boot off) |
| Remote OTA takeover (leaked secret) | remote reflash / takeover | BrakTooth CVE-2021-28139 (OTA-less RCE in the wild) |
| Credential-less crash attempt | over-the-air DoS | CVE-2019-12588 (WiFi), SweynTooth CVE-2020-13594 (BLE) |

(Honest note: BrakTooth and SweynTooth are Bluetooth; our twin is WiFi. They are
cited as evidence of the *class*, remote, unauthenticated compromise of this
chip, and the WiFi CVEs 2019-12586/12588 show the same class on the radio our
twin actually uses.)

## The mitigations (the "protected environment")

1. **Enable flash encryption + secure boot.** Then a flash dump is ciphertext and
   a modified or cloned image will not boot, this kills the dump, clone and
   implant chain. (And note CVE-2019-17391: even these can be glitched on old
   silicon, which is why physical protection still matters.)
2. **Never hardcode secrets;** provision per-device keys in protected storage, so
   one leak is not a fleet-wide key. (Mirai's lesson.)
3. **Authenticated, *signed* OTA** with a key that is not recoverable from the
   device, so a leaked token cannot be replayed to reflash the fleet.
4. **Physical and network protection:** keep MCUs out of untrusted hands, segment
   them off the main network, and keep ESP-IDF patched (the crash/RCE CVEs above
   are all fixed in later IDF releases).
5. **Robustness:** watchdogs and auto-reboot so a crash is not a permanent
   deadlock; rate-limit and bound every network handler.

**Bottom line:** an unprotected microcontroller is a few seconds (physical) or a
single crafted packet (radio) away from being read, crashed, cloned, or owned.
The defences exist, but they are *off by default*. "Deploy it in a protected
environment, with its security features enabled" is not best-practice advice, it
is the difference between the attacks above working and failing.

## Sources

- Espressif advisory, CVE-2019-15894 (Secure Boot / fault injection): <https://www.espressif.com/en/news/Espressif_Security_Advisory_Concerning_Fault_Injection_and_Secure_Boot>
- Espressif advisory, CVE-2019-17391 (eFuse / key extraction): <https://www.espressif.com/en/news/Security_Advisory_Concerning_Fault_Injection_and_eFuse_Protections>
- LimitedResults, ESP32 flash-encryption & secure-boot key extraction: <https://blog.adafruit.com/2019/11/18/esp32-flash-encryption-and-sec-boot-keys-extraction-esp32-encryption-pwn-limitedresults/>
- Raelize, "Bypassing Secure Boot using EMFI": <https://raelize.com/blog/espressif-systems-esp32-bypassing-sb-using-emfi/>
- CVE-2025-27840 (undocumented HCI commands), NVD: <https://nvd.nist.gov/vuln/detail/CVE-2025-27840>
- BleepingComputer on the ESP32 HCI commands (and the "backdoor" downgrade): <https://www.bleepingcomputer.com/news/security/undocumented-commands-found-in-bluetooth-chip-used-by-a-billion-devices/>
- ESP8266/ESP32 WiFi crash CVE-2019-12588: <https://osv.dev/vulnerability/CVE-2019-12588>
- ESP-hosted WiFi driver DoS, CVE-2026-17054: <https://app.opencve.io/cve/CVE-2026-17054>
- SweynTooth disclosure (BLE crashes/deadlocks), CVE-2020-13594/13595: <https://asset-group.github.io/disclosures/sweyntooth/sweyntooth.pdf>
- BrakTooth disclosure (ESP32 RCE, CVE-2021-28139): <https://asset-group.github.io/disclosures/braktooth/disclosure.html>
- The Hacker News on BrakTooth: <https://thehackernews.com/2021/09/new-braktooth-flaws-leave-millions-of.html>
- Mirai / Dyn 2016 analysis: <https://mse238blog.stanford.edu/2018/07/clairemw/the-2016-dyn-attack-and-its-lessons-for-iot-security/>
