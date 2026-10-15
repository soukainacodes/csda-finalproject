"""Synthetic beacon generator.

Purpose: let the whole Watcher + arms-race pipeline run and be validated WITHOUT
hardware, and give the attacker a surrogate to evolve against offline. The record
schema is identical to the sniffer's real output, so the exact same downstream
code runs live by swapping this for a real capture.

Model: the REAL router has a fixed fingerprint. The TWIN is rendered from a
disguise "genome". The closer the genome mimics the real router, the harder it is
to detect, EXCEPT beacon-timing jitter, which has a hardware floor the ESP32 twin
cannot go below. That residual is what lets the Watcher recover after retraining,
which is the whole point of the H4 arms-race curve.
"""
import random

# ---- the real router's (fixed) fingerprint ---------------------------------
REAL_IE_SET   = [0, 1, 3, 5, 42, 45, 48, 50, 61, 127, 221]
REAL_VENDORS  = ["00:50:f2"]
REAL_CAP      = 0x1431
REAL_BI       = 100
REAL_JITTER   = 2200      # us; a real AP keeps fairly tight beacon timing
REAL_RSSI     = -45

# The twin's hardware floor: the ESP32 beacon timing wobbles more than a real AP,
# but the distributions OVERLAP, so beacon jitter alone is not a perfect
# separator. That overlap is what forces the Watcher to also rely on the
# evadable features (BSSID bit, vendor IE, IE set, beacon interval), which in turn
# is what lets the attacker temporarily evade a detector trained on older rounds,
# producing the arms-race zig-zag until the jitter floor finally pins it.
TWIN_JITTER_FLOOR = 3500  # us


def default_genome() -> dict:
    """Round-0 disguise: deliberately obvious, so the Watcher wins round 1."""
    return {
        "beacon_interval": 100,
        "tx_power": 80,         # loud (out-signalling)
        "vendor_ie": False,     # missing the real vendor IE
        "laa": True,            # locally-administered BSSID (a tell)
        "match_ie_set": False,  # reduced IE set
        "timing_jitter_us": 12000,
    }


def genome_space() -> dict:
    return {
        "beacon_interval": [100, 102, 150, 200],
        "tx_power": [40, 60, 70, 80, 84],
        "vendor_ie": [False, True],
        "laa": [True, False],
        "match_ie_set": [False, True],
        "timing_jitter_us": [12000, 9000, 7000, TWIN_JITTER_FLOOR],
    }


def _twin_fingerprint(genome):
    ies = list(REAL_IE_SET) if genome["match_ie_set"] else [0, 1, 3, 5, 42, 48]
    vendors = list(REAL_VENDORS) if genome["vendor_ie"] else []
    cap = REAL_CAP if genome["match_ie_set"] else 0x0421
    jitter = max(genome["timing_jitter_us"], TWIN_JITTER_FLOOR)
    rssi = max(-85, min(-30, -90 + genome["tx_power"]))  # loud -> stronger
    return ies, vendors, cap, jitter, rssi


def _emit(bssid, ssid, start_t, n, bi, jitter, rssi, ies, vendors, cap, ch=6):
    recs, t = [], start_t
    for _ in range(n):
        t += int(bi * 1024 + random.gauss(0, jitter))
        recs.append({
            "k": "beacon", "t": t, "ch": ch,
            "rssi": int(rssi + random.gauss(0, 3)),
            "bssid": bssid, "sa": bssid, "ssid": ssid,
            "bi": bi, "cap": cap, "ies": ies, "vendors": vendors,
        })
    return recs


def generate_round(genome, n_each, ssid, real_bssid, twin_bssid, seed=None):
    """One capture window seeing BOTH the real router and the twin."""
    if seed is not None:
        random.seed(seed)
    real = _emit(real_bssid, ssid, 0, n_each, REAL_BI, REAL_JITTER,
                 REAL_RSSI, REAL_IE_SET, REAL_VENDORS, REAL_CAP)
    ies, vendors, cap, jitter, rssi = _twin_fingerprint(genome)
    # the twin's BSSID first octet reflects the LAA genome bit
    tb = twin_bssid.split(":")
    tb[0] = "02" if genome["laa"] else "3c"
    tw_bssid = ":".join(tb)
    twin = _emit(tw_bssid, ssid, 0, n_each, genome["beacon_interval"], jitter,
                 rssi, ies, vendors, cap)
    return real + twin
