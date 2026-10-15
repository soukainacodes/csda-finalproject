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


def push_ota(image_path: str, url=None) -> str:
    with open(image_path, "rb") as f:
        data = f.read()
    r = requests.post(_url("/ota", url), data=data,
                      headers={"Content-Type": "application/octet-stream"}, timeout=120)
    r.raise_for_status()
    return r.text
