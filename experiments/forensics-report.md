# AL-GHUL post-mortem (flash forensics)

Source dump: `..\experiments\alghul_flash.bin`  (4194304 bytes)

Flash encryption was OFF, so everything below was recovered in **cleartext** with a single `esptool read_flash`.


## Recovered network
- Cloned SSID: Kaffi_FRI

## Recovered secrets (plaintext)
- control/kill token: `ghoul-begone-2026`
- WiFi password (PSK): `bestcoffee`

## Saved disguise (NVS)
- _none found_

## The victim diary (who the twin intercepted)
- `28:d0:43:06:46:e1`

## The lesson
Everything above is the case for flash encryption + secure boot. With them on, this dump is ciphertext and this page is blank.
