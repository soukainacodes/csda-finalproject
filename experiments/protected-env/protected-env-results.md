# Protected environment: measured security posture of the microcontrollers (2026-11-05)

All measurements are READ-ONLY on my own ESP32-S3 boards (twin COM18, Watcher COM15).
No eFuses were burned, no firmware overwritten; the authenticated kill was never actually
sent (only a wrong-token attempt). Tools: esptool / espefuse v4.12.0.

## Measured scenarios

D1  Silicon security state (eFuses, espefuse summary)
    - Twin  : SPI_BOOT_CRYPT_CNT = Disable (flash encryption OFF); SECURE_BOOT_EN = False;
              DIS_PAD_JTAG / DIS_USB_JTAG = False (JTAG ENABLED); download mode open.
    - Watcher: identical, flash encryption OFF, Secure Boot False, JTAG enabled.
    => Both boards (default ESP32-S3) have every hardware protection OFF. Systemic.
    Logs: efuse-summary-twin.txt, efuse-summary-watcher.txt

D2  Forensic extraction (esptool read_flash 0x0-0x400000, 4 MB in 96.6 s)
    - Recovered in PLAINTEXT from the dump: Kaffi_FRI (cloned SSID), bestcoffee (cloned WPA2
      password), ghoul-begone-2026 (the kill / control token). Each 1 occurrence.
    => flash-encryption-off means the dump hands over the network password and the kill token.
    Log: flash-dump-secrets-twin.txt  (raw 4 MB dump kept local, not committed: contains secrets)

D3  Unauthenticated takedown attempt (wrong kill token over serial)
    - KILL wrong-token-attempt -> KILL_ERR bad_token ; PING -> PONG (twin still alive).
    => the kill IS authenticated (software protection present); a random attacker cannot wipe it.
    Log: kill-auth-test-twin.txt

## Comparison table (measured, not asserted)

| Protection | What it stops | Twin | Watcher | Consequence measured |
|---|---|---|---|---|
| Flash encryption | reading flash secrets | OFF | OFF | dump recovered password + kill token |
| Secure Boot v2 | unsigned / OTA firmware | OFF | OFF | any reflash accepted (we reflashed both) |
| JTAG / debug lock | debugger memory read | OFF | OFF | debug port open |
| Download-mode lock | serial reflash / dump | OFF | OFF | the 4 MB dump succeeded |
| Kill-token auth (software) | unauthenticated takedown | PRESENT | n/a | wrong token rejected (KILL_ERR) |

## The chain (weakest link)
The kill is token-authenticated (D3, good), BUT the token sits in plaintext flash (D1/D2, flash
encryption off), so the dump recovers it (D2). The software protection is undone by the missing
hardware one. Defense in depth fails at its weakest layer.

## Protection cuts both ways (the honest twist)
A HARDENED twin would resist this takedown entirely:
- flash encryption -> the dump returns ciphertext, no password, no token;
- Secure Boot + signed OTA + anti-rollback -> an unsigned kill image / malicious OTA is REJECTED;
- JTAG lock -> no debugger memory read.
So the same hardening that should protect honest IoT devices would also shield a well-built evil
twin from remote takedown. Against a hardened rogue, hacking back fails; you are left with
DETECTION (the Watcher) and PHYSICAL response (find by signal, unplug). This is why the network
-level detector is the real defence.

## Where real devices failed (cited, not re-measured)
Mirai (2016): ~150k devices owned via default/hardcoded credentials. BrakTooth (CVE-2021-28139):
radio-range code execution on ESP32. Fault injection (CVE-2019-17391): recovers the flash-
encryption key even when enabled, so "protected" is relative and newer silicon adds mitigations.

## Honest limits
Read-only snapshot of two of my own boards; the hardened-device behaviour is reasoned/cited, not
re-measured (enabling Secure Boot / flash encryption burns irreversible eFuses and risks bricking
the board, so it was deliberately not done).
