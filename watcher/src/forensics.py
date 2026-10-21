"""Post-mortem forensics on a killed AL-GHUL.

After the Watcher neutralises the twin, we dump its flash and read its diary.
Because the ESP32 ships with flash encryption OFF (the weakness this whole
project is about), a plain `esptool read_flash` yields the firmware and every
secret in cleartext. This tool parses that dump and recovers:

  - the cloned network name and its WiFi password   (plaintext)
  - the control / kill token                          (plaintext)
  - the saved disguise                                (NVS)
  - the victim "diary": every MAC that joined the clone, logged to NVS by the
    twin's relaylog (metadata only, never payloads)

Usage:
  # analyse a dump you already have
  python -m src.forensics --dump ..\experiments\alghul_flash.bin

  # or pull the dump first (needs esptool on PATH, e.g. an ESP-IDF shell)
  python -m src.forensics --read --port COM11 --size 0x400000
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

from . import config

PRINTABLE = re.compile(rb"[\x20-\x7e]{4,}")
MAC = re.compile(r"\b([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b")


def extract_strings(data: bytes):
    return [m.group().decode("ascii", "replace") for m in PRINTABLE.finditer(data)]


def read_flash(port: str, size: str, out: Path) -> bool:
    """Dump flash with esptool, if it is available."""
    for exe in (["esptool.py"], [sys.executable, "-m", "esptool"]):
        try:
            cmd = exe + ["--port", port, "read_flash", "0x0", size, str(out)]
            print("  running:", " ".join(cmd))
            subprocess.run(cmd, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    print("  esptool not found. Run this from an ESP-IDF shell, or dump manually:")
    print(f"    esptool.py --port {port} read_flash 0x0 {size} dump.bin")
    return False


def analyse(dump: Path) -> dict:
    data = dump.read_bytes()
    strings = extract_strings(data)
    blob = "\n".join(strings)

    found = {"ssids": [], "secrets": [], "victims": [], "disguise": None}

    # the cloned SSID (what the twin broadcast). Match the configured SSID, and
    # any recovered run that looks like it (non-ASCII bytes split a string, so a
    # name like "Kaffi_Frí" surfaces as "Kaffi_Fr" in a plain strings pass).
    cfg_ssid = config.REAL_ROUTER_SSID
    prefix = (cfg_ssid[:5] if cfg_ssid not in ("", "YOUR_LAB_SSID") else "Kaffi").lower()
    for s in strings:
        sl = s.lower()
        if (prefix and sl.startswith(prefix)) or (cfg_ssid not in ("", "YOUR_LAB_SSID") and cfg_ssid in s):
            if s not in found["ssids"]:
                found["ssids"].append(s)

    # secrets: the control token and anything sitting next to password-ish labels
    tok = config.ALGHUL_CONTROL_TOKEN
    if tok and tok != "CHANGE_ME_pick_a_secret" and tok in blob:
        found["secrets"].append(("control/kill token", tok))
    psk = getattr(config, "REAL_ROUTER_PSK", "")
    if psk and psk not in ("", "YOUR_LAB_WPA2_PASSWORD") and psk in blob:
        found["secrets"].append(("WiFi password (PSK)", psk))
    for s in strings:
        if s.lower() in ("password", "psk") or "token" in s.lower():
            continue
        # heuristics for a WPA2 PSK: 8..63 printable, not an obvious label/path
        if 8 <= len(s) <= 63 and " " not in s and "/" not in s and "=" not in s \
           and re.search(r"[a-z]", s) and s not in [v for _, v in found["secrets"]]:
            # only surface a few strong candidates near known markers
            pass

    # the saved disguise JSON (stored by disguise_save as a string in NVS)
    m = re.search(r'\{[^{}]*"bssid"[^{}]*\}', blob)
    if m:
        found["disguise"] = m.group()

    # the victim diary: the NVS "victims" string is a run of "mac;mac;..."
    victims = [mm.group() for mm in MAC.finditer(blob)]
    # de-dup, drop broadcast / all-zero / the twin's own default AP bssid
    drop = {"ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00", "02:a1:00:00:00:01"}
    seen = []
    for v in victims:
        vl = v.lower()
        if vl not in drop and vl not in seen:
            seen.append(vl)
    found["victims"] = seen
    return found


def report(found: dict, dump: Path) -> str:
    lines = []
    lines.append("# AL-GHUL post-mortem (flash forensics)\n")
    lines.append(f"Source dump: `{dump}`  ({dump.stat().st_size} bytes)\n")
    lines.append("Flash encryption was OFF, so everything below was recovered in "
                 "**cleartext** with a single `esptool read_flash`.\n")

    lines.append("\n## Recovered network")
    lines.append("- Cloned SSID: " + (", ".join(found["ssids"]) or "_none found_"))

    lines.append("\n## Recovered secrets (plaintext)")
    if found["secrets"]:
        for label, val in found["secrets"]:
            lines.append(f"- {label}: `{val}`")
    else:
        lines.append("- _none matched config markers (pass a real dump; the token "
                     "and PSK appear verbatim)_")

    lines.append("\n## Saved disguise (NVS)")
    lines.append("- " + (f"`{found['disguise']}`" if found["disguise"] else "_none found_"))

    lines.append("\n## The victim diary (who the twin intercepted)")
    if found["victims"]:
        for v in found["victims"]:
            lines.append(f"- `{v}`")
    else:
        lines.append("- _no victim MACs in this dump (the twin logs them to NVS as "
                     "clients join; an empty list means none joined before the kill)_")

    lines.append("\n## The lesson")
    lines.append("Everything above is the case for flash encryption + secure boot. "
                 "With them on, this dump is ciphertext and this page is blank.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Post-mortem forensics on a killed AL-GHUL")
    ap.add_argument("--dump", default=None, help="path to a flash dump to analyse")
    ap.add_argument("--read", action="store_true", help="dump flash first via esptool")
    ap.add_argument("--port", default="COM11", help="serial port for --read")
    ap.add_argument("--size", default="0x400000", help="bytes to read for --read")
    args = ap.parse_args()

    if args.read:
        dump = config.EXPERIMENTS / "alghul_flash.bin"
        if not read_flash(args.port, args.size, dump):
            sys.exit(2)
    elif args.dump:
        dump = Path(args.dump)
    else:
        print("Give a dump with --dump, or pull one with --read --port COMx.")
        sys.exit(1)

    if not dump.exists():
        print(f"dump not found: {dump}")
        sys.exit(1)

    found = analyse(dump)
    text = report(found, dump)
    out = config.EXPERIMENTS / "forensics-report.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n  saved: {out}")


if __name__ == "__main__":
    main()
