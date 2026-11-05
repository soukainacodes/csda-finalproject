#!/usr/bin/env python3
"""Session-cookie hijack / 2FA-bypass demonstration. EDUCATIONAL, LAB ONLY.

CSDA project (RU). Shows WHY stealing a session cookie defeats two-factor auth:
the cookie is a bearer token the server mints AFTER the password + 2FA succeed, so
replaying it skips both. An evil-twin MITM captures it whenever the session rides
cleartext HTTP (or TLS that has been stripped, or decrypted via a rogue CA the
victim was tricked into trusting). Proper HTTPS with a Secure cookie prevents it,
because the cookie never crosses the wire in the clear.

This runs against a SELF-CONTAINED fake site ("MyBank"), never a real service.

  python demo_session.py --demo          # run the whole capture+replay narrative
  python demo_session.py --serve --port 8081   # just host the demo site (for a live run)
"""
from __future__ import annotations
import argparse, http.client, secrets, threading, time, urllib.parse
from flask import Flask, request, redirect, make_response

app = Flask(__name__)
SESSIONS: dict[str, str] = {}          # session-token -> username (the server's memory)
USERS = {"alice": {"pw": "hunter2", "otp": "490213", "balance": "4,820.17 EUR"}}

BANNER = ('<div style="position:fixed;top:0;left:0;right:0;background:#b00020;color:#fff;'
          'font:600 12px sans-serif;text-align:center;padding:5px">EDUCATIONAL LAB DEMO '
          '&mdash; fake bank, not a real service (CSDA / RU)</div><div style="height:30px"></div>')

LOGIN = BANNER + """<h2>MyBank &mdash; sign in</h2>
<form method=post action=/login>
 Username <input name=user value=alice><br><br>
 Password <input name=pw type=password><br><br>
 2FA code <input name=otp><br><br><button>Sign in</button></form>"""


def account_html(user: str) -> str:
    u = USERS[user]
    return (BANNER + f"<h2>MyBank</h2><p>Welcome back, <b>{user}</b>.</p>"
            f"<p>Account balance: <b>{u['balance']}</b></p>"
            "<p style='color:#555'>This page asked for no password and no 2FA. "
            "The session cookie alone proved who you are.</p>")


@app.get("/")
def home():
    return LOGIN


@app.post("/login")
def login():
    user = request.form.get("user", ""); pw = request.form.get("pw", ""); otp = request.form.get("otp", "")
    u = USERS.get(user)
    if not u or pw != u["pw"] or otp != u["otp"]:
        return BANNER + "<p>Login failed (need password AND correct 2FA code).</p>", 401
    token = secrets.token_hex(16)
    SESSIONS[token] = user            # the server now trusts this token = this user
    resp = make_response(redirect("/account"))
    # NOTE: no Secure / HttpOnly here on purpose -> over plain HTTP this cookie is
    # visible to any MITM. A real bank sets Secure+HttpOnly and serves over HTTPS.
    resp.set_cookie("session", token)
    return resp


@app.get("/account")
def account():
    token = request.cookies.get("session", "")
    user = SESSIONS.get(token)
    if not user:
        return BANNER + "<p>Not logged in.</p>", 401
    return account_html(user)


# --------------------------------------------------------------------------- #
def _raw(port: int, method: str, path: str, headers=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    data = r.read().decode("utf-8", "replace")
    setcookie = r.getheader("Set-Cookie")
    c.close()
    return r.status, setcookie, data


def run_demo(port: int):
    threading.Thread(target=lambda: app.run(host="127.0.0.1", port=port,
                     threaded=True, use_reloader=False), daemon=True).start()
    time.sleep(1.2)
    line = "-" * 68
    print(line); print("SESSION-COOKIE HIJACK DEMO  (educational, fake bank)"); print(line)

    # 1) VICTIM authenticates fully: password + correct 2FA code
    body = urllib.parse.urlencode({"user": "alice", "pw": "hunter2", "otp": "490213"})
    st, setck, _ = _raw(port, "POST", "/login",
                        {"Content-Type": "application/x-www-form-urlencoded"}, body)
    cookie = (setck or "").split(";")[0]    # e.g. "session=ab12..."
    print(f"\n[VICTIM]  logs in with password + 2FA code 490213  -> HTTP {st}")
    print(f"[VICTIM]  server hands back a session cookie:")
    print(f"              Set-Cookie: {setck}")

    # 2) ATTACKER (evil-twin MITM) sees that exact cookie in the cleartext HTTP
    print(f"\n[ATTACKER] on the twin, the victim's next request crosses in the clear:")
    print(f"              GET /account HTTP/1.1")
    print(f"              Cookie: {cookie}      <-- stolen here")

    # 3) ATTACKER replays ONLY the cookie, from their own machine, no creds
    st, _, page = _raw(port, "GET", "/account", {"Cookie": cookie})
    got = "Welcome back" in page
    bal = page.split("Account balance: <b>")[1].split("</b>")[0] if got else "-"
    print(f"\n[ATTACKER] replays the stolen cookie alone (no password, no 2FA) -> HTTP {st}")
    print(f"[ATTACKER] ACCOUNT TAKEN OVER: logged in as 'alice', balance {bal}" if got
          else "[ATTACKER] failed")

    # 4) CONTROL: without the cookie, the same request is rejected
    st, _, _ = _raw(port, "GET", "/account", {})
    print(f"\n[CONTROL]  same request with NO cookie            -> HTTP {st} (denied)")
    print(f"\n==> The cookie, not the password, is the key. 2FA was bypassed because the")
    print(f"    token was issued AFTER 2FA. HTTPS + Secure cookie would stop the capture.")
    print(line)


def main():
    ap = argparse.ArgumentParser(description="session-cookie hijack demo (lab only)")
    ap.add_argument("--demo", action="store_true", help="run the capture+replay narrative")
    ap.add_argument("--serve", action="store_true", help="just host the demo site")
    ap.add_argument("--port", type=int, default=8081)
    args = ap.parse_args()
    if args.demo:
        run_demo(args.port)
    else:
        print(f"[*] MyBank demo (lab only) on http://0.0.0.0:{args.port}")
        app.run(host="0.0.0.0", port=args.port, threaded=True)


if __name__ == "__main__":
    main()
