"""The finisher: push the KILL image to AL-GHUL over its own OTA channel.

This is an authenticated-by-design command to a board you own and built to obey
it, not an exploit of anyone else's device. It uses no deauth and no jamming.
After the push, AL-GHUL boots the kill image, erases its flash, and goes dark;
only a physical USB re-flash brings it back.

Usage:
  python -m src.killswitch --image ../firmware/kill/build/kill.bin --yes
"""
import argparse
import sys

from . import control


def main():
    ap = argparse.ArgumentParser(description="Push the AL-GHUL kill image over OTA")
    ap.add_argument("--image", required=True, help="path to kill.bin")
    ap.add_argument("--url", default=None, help="override AL-GHUL control URL")
    ap.add_argument("--yes", action="store_true", help="confirm the wipe")
    args = ap.parse_args()

    if not args.yes:
        print("This wipes AL-GHUL (your own board). Re-run with --yes to confirm.")
        sys.exit(1)

    print("pushing kill image...")
    print(control.push_ota(args.image, args.url))
    print("AL-GHUL should now wipe itself and go dark.")


if __name__ == "__main__":
    main()
