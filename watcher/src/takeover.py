"""The climax: once the Watcher is sure, it TAKES OVER AL-GHUL, not just kills it.

This is the escalation of the finisher. It runs against a board you own, over the
board's OWN control channel, using the shared secret in config.ALGHUL_CONTROL_TOKEN.
It is deliberately the *tame* version of a danger that, in the wild, has been fully
unauthenticated (BrakTooth CVE-2021-28139 = over-the-air RCE on the ESP32 with no
pairing). See docs/MCU_SECURITY.md for the real incidents behind each move.

Escalation ladder (choose with --level):
  reach     just prove control-plane access (GET /status)
  prove     flip the twin's disguise live, visible proof we can command it
  own       reflash it over the air with operator firmware (OTA takeover)  [needs --image]
  kill      trigger its self-wipe (/kill); the board erases itself and goes dark

Each higher level runs the ones below it first, so "own" also does reach+prove.

Usage:
  python -m src.takeover --level reach
  python -m src.takeover --level prove
  python -m src.takeover --level own  --image ../firmware/al_ghul/build/al_ghul.bin --yes
  python -m src.takeover --level kill --yes

The credential-less crash (one crafted 802.11 frame, no secret at all) is the
third real-world class. It needs a monitor-mode injector, not this control
channel, so it is run from the lab, not here. See docs/MCU_SECURITY.md
(CVE-2019-12586 / CVE-2019-12588) and docs/LAB_RUNBOOK.md for that step.
"""
import argparse
import json
import sys
import time

from . import control, config

LEVELS = ["reach", "prove", "own", "kill"]


def _banner(txt):
    print("\n" + "=" * 60 + f"\n  {txt}\n" + "=" * 60)


def do_reach(url):
    _banner("REACH  -  can the Watcher even talk to the twin?")
    st = control.get_status(url)
    print(json.dumps(st, indent=2))
    print(f"\n  -> reached AL-GHUL at {url or config.ALGHUL_CONTROL_URL} "
          f"(running on partition '{st.get('running_partition','?')}').")
    return st


def do_prove(url):
    _banner("PROVE  -  command it live (flip its disguise)")
    before = control.get_status(url).get("disguise", {})
    # Toggle a harmless, visible field so the change is observable from the sniffer.
    new_interval = 102 if before.get("beacon_interval") != 102 else 200
    print(f"  current beacon_interval = {before.get('beacon_interval')}; "
          f"commanding -> {new_interval}")
    control.push_disguise({"beacon_interval": new_interval}, url)
    time.sleep(2.0)
    after = control.get_status(url).get("disguise", {})
    print(f"  now beacon_interval = {after.get('beacon_interval')}")
    print("\n  -> the twin obeyed a remote command. We own its behaviour.")


def do_own(url, image, token):
    _banner("OWN  -  reflash it over the air (OTA takeover)")
    if not image:
        print("  --image is required for level 'own' (the firmware to push).")
        sys.exit(2)
    print(f"  pushing {image} to /ota (token-authenticated)...")
    resp = control.push_ota(image, url, token)
    print(f"  twin replied: {resp.strip()}")
    print("\n  -> the board is now running firmware WE chose. Full takeover.")


def do_kill(url, token):
    _banner("KILL  -  make it erase itself and go dark")
    resp = control.send_kill(url, token)
    print(f"  twin replied: {resp.strip()}")
    print("\n  -> AL-GHUL is wiping flash. Only a physical USB re-flash revives it.")


def main():
    ap = argparse.ArgumentParser(description="Watcher -> AL-GHUL takeover demo")
    ap.add_argument("--level", choices=LEVELS, default="reach",
                    help="how far up the escalation ladder to go")
    ap.add_argument("--image", default=None, help="firmware .bin for level 'own'")
    ap.add_argument("--url", default=None, help="override AL-GHUL control URL")
    ap.add_argument("--token", default=None,
                    help="control token (overrides config; pass at runtime to keep "
                         "the real secret out of tracked files)")
    ap.add_argument("--yes", action="store_true",
                    help="required for destructive levels (own, kill)")
    args = ap.parse_args()

    if args.level in ("own", "kill") and not args.yes:
        print(f"Level '{args.level}' changes/destroys your board. Re-run with --yes.")
        sys.exit(1)

    target = LEVELS.index(args.level)
    # run every level up to and including the chosen one
    if target >= 0:
        do_reach(args.url)
    if target >= 1:
        do_prove(args.url)
    if target >= 2:
        do_own(args.url, args.image, args.token)
    if target >= 3:
        do_kill(args.url, args.token)

    print("\nDone.")


if __name__ == "__main__":
    main()
