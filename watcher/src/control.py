"""HTTP client for AL-GHUL's control plane (status, disguise, OTA).

Calls retry across the brief window when a disguise change restarts the twin's
WiFi and the laptop has to re-associate to the clone.
"""
import time
import requests
from . import config


def _url(path, url=None):
    base = url or config.ALGHUL_CONTROL_URL
    return base.rstrip("/") + path


def _retry(fn, attempts=20, gap=2.0):
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except requests.RequestException as e:
            last = e
            time.sleep(gap)
    raise last


def get_status(url=None) -> dict:
    def go():
        r = requests.get(_url("/status", url), timeout=5)
        r.raise_for_status()
        return r.json()
    return _retry(go)


def push_disguise(disguise: dict, url=None) -> dict:
    def go():
        r = requests.post(_url("/disguise", url), json=disguise, timeout=10)
        r.raise_for_status()
        return r.json()
    return _retry(go)


def push_ota(image_path: str, url=None, token=None) -> str:
    """Reflash AL-GHUL over the air. /ota is token-protected, so the secret is
    required, this is the remote-takeover primitive (push operator firmware) and
    also how the kill image is delivered."""
    tok = token if token is not None else config.ALGHUL_CONTROL_TOKEN
    with open(image_path, "rb") as f:
        data = f.read()
    r = requests.post(_url("/ota", url) + f"?token={tok}", data=data,
                      headers={"Content-Type": "application/octet-stream"}, timeout=120)
    r.raise_for_status()
    return r.text


def send_kill_serial(port, token=None, baud=115200) -> str:
    """Trigger AL-GHUL's kill over USB serial ("KILL <token>"), independent of the
    WiFi control plane. Reliable even when the laptop can't join the twin's AP."""
    import serial
    tok = token if token is not None else config.ALGHUL_CONTROL_TOKEN
    with serial.Serial(port, baud, timeout=2) as s:
        time.sleep(0.3)
        s.write(("KILL " + tok + "\n").encode())
        s.flush()
        time.sleep(0.6)
        reply = s.read(256).decode("utf-8", "replace").strip()
        # Hold the port open through the board's death sequence (rattle + wipe +
        # tombstone + reset, ~3s). Closing the USB port pulses a reset, so closing
        # it mid-sequence would reboot the board BEFORE it sets the kill marker and
        # the twin would come back. Waiting lets it reach the dark state first.
        time.sleep(4.0)
        return reply


def send_kill(url=None, token=None) -> str:
    """Trigger AL-GHUL's self-wipe via the token-protected /kill endpoint (no image
    needed). The board erases NVS/otadata/the other slot, invalidates itself, and
    stays dark until a physical USB re-flash."""
    tok = token if token is not None else config.ALGHUL_CONTROL_TOKEN
    r = requests.get(_url("/kill", url) + f"?token={tok}", timeout=10)
    r.raise_for_status()
    return r.text
