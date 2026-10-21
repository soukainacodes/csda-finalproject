"""The "what the attacker sees" live feed.

AL-GHUL's danger-demo build logs every domain the connected phone looks up to its
USB console as `DNSSPY <name>`. This reads that stream and shows, in real time,
the victim's whole browsing map, even though every connection is HTTPS-encrypted.
Names only, never payloads. For the student's OWN devices in the isolated lab,
to demonstrate the threat the Watcher defends against.

Usage:
  python -m src.spyfeed                 # reads AL-GHUL on COM12
  python -m src.spyfeed --port COM12
"""
import argparse
import re
import time
from collections import Counter

LINE = re.compile(r"DNSSPY\s+([A-Za-z0-9._-]+)")

# Noise we fold away so the human-meaningful sites stand out.
NOISE = ("in-addr.arpa", "ip6.arpa", "_tcp", "_udp", "_dns-sd", ".local",
         "connectivitycheck", "captive", "gvt1.com", "gvt2.com")

# A few recognisable services, to narrate the demo ("...they bank at...").
NOTABLE = {
    "landsbankinn": "a bank", "arionbanki": "a bank", "islandsbanki": "a bank",
    "instagram": "Instagram", "facebook": "Facebook", "whatsapp": "WhatsApp",
    "tiktok": "TikTok", "snapchat": "Snapchat", "tinder": "a dating app",
    "gmail": "Gmail", "google": "Google", "youtube": "YouTube",
    "icloud": "Apple/iCloud", "netflix": "Netflix", "spotify": "Spotify",
    "reddit": "Reddit", "x.com": "X/Twitter", "twitter": "X/Twitter",
    "paypal": "PayPal", "amazon": "Amazon", "proton": "ProtonMail",
}


def notable_for(name):
    low = name.lower()
    for key, label in NOTABLE.items():
        if key in low:
            return label
    return None


def main():
    ap = argparse.ArgumentParser(description="Live 'what the twin sees' DNS feed")
    ap.add_argument("--port", default="COM12", help="AL-GHUL USB port")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()

    import serial
    seen = Counter()
    first_seen = {}
    t0 = time.time()

    print("\n  === WHAT THE TWIN SEES ===")
    print("  Every domain the connected phone reaches shows up here, live.")
    print("  (HTTPS hides the contents; it cannot hide WHERE you go.)\n")

    try:
        # Open WITHOUT asserting DTR/RTS, so we don't reset AL-GHUL (its native
        # USB-JTAG reboots on a normal open, which would drop the victim).
        s = serial.Serial()
        s.port = args.port
        s.baudrate = args.baud
        s.timeout = 0.5
        s.dtr = False
        s.rts = False
        s.open()
    except Exception as e:
        print("  could not open", args.port, ":", e)
        return
    time.sleep(0.3)
    s.reset_input_buffer()

    try:
        while True:
            raw = s.readline()
            if not raw:
                continue
            m = LINE.search(raw.decode("utf-8", "replace"))
            if not m:
                continue
            name = m.group(1).rstrip(".")
            if not name or any(n in name.lower() for n in NOISE):
                continue
            seen[name] += 1
            if name not in first_seen:
                first_seen[name] = time.time() - t0
                tag = notable_for(name)
                flag = f"   <-- {tag}" if tag else ""
                print(f"  [{first_seen[name]:6.1f}s]  the phone just reached  {name}{flag}")
    except KeyboardInterrupt:
        pass
    finally:
        s.close()
        print(f"\n  === the twin saw {len(seen)} distinct domains from this one phone ===")
        notable = [(n, notable_for(n)) for n in seen if notable_for(n)]
        if notable:
            print("  recognisable services it now knows this person uses:")
            for n, label in sorted(set(notable)):
                print(f"    - {label:16}  ({n})")
        print("  All of this was readable with the traffic fully HTTPS-encrypted.\n")


if __name__ == "__main__":
    main()
