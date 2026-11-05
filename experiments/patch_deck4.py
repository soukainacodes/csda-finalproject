#!/usr/bin/env python3
"""Four framing fixes from the external critique (content-keyed, no image touch):
 1. device-independent vs flattered detectors, 2. the one crisp contribution,
 3. detection-is-not-defense, 4. the time-to-detect distribution (not a point est.)."""
import sys
from pathlib import Path
P = Path(sys.argv[1]); h = P.read_text(encoding="utf-8")


def sub(old, new):
    global h
    assert h.count(old) == 1, f"anchor not unique/found: {old[:60]!r}"
    h = h.replace(old, new, 1)


# Fix 4: time-to-detect distribution in the on-board figure caption
sub('<figcaption>Figure 5. On-board detection of the exact clone over a 150&nbsp;s run: first detect ~6&nbsp;s, held ~83% of the time, clears ~8&nbsp;s after a radio leaves. Source: watcher-onboard-sum-Btiming; onboard-results-2026-11-05.md.</figcaption>',
    '<figcaption>Figure 5. On-board detection of the exact clone (one 150&nbsp;s run shown). Detection latency, clear-to-detect, across 9 runs: median 3&nbsp;s, range 2&ndash;10&nbsp;s; detection held ~83% of the time. Longer first-encounter times reflect the hopping Watcher\'s channel sampling, not slow detection. Source: watcher-onboard-sum-*.</figcaption>')

# Fix 1: device-independent vs flattered, appended to the on-board table caption
sub('<caption>Table 1. On-board verdict. Only the physical detectors catch the exact clone (B); neither false-alarms on a lone AP (C). Detection confirmed under WPA2 and WPA2+PMF.</caption>',
    '<caption>Table 1. On-board verdict. Only the physical detectors catch the exact clone (B); neither false-alarms on a lone AP (C). The un-evadable core is device-independent, two clocks under one BSSID, double beacon rate, a second sequence counter; the IE and per-radio-skew tells are flattered by this bare-ESP32 attacker (see limits).</caption>')

# Fix 2+3: expand the single-pair limit (laptop flatters) and add detection-is-not-defense
sub('<li><b>One Watcher, one real AP, one twin.</b> A legitimate enterprise network has many BSSIDs for one name, where the naive count rule would false-positive; that regime is untested, and the physical detectors still need validation against genuinely identical APs.</li>',
    '<li><b>One Watcher, one real AP, one twin, and the real AP is a laptop hotspot.</b> A real enterprise network has many BSSIDs for one name (the naive rule would false-positive, untested). And a rich Windows softAP against a bare ESP32 <b>flatters</b> the IE and per-radio-skew detectors; the honest, un-evadable core is the device-independent tells (two clocks under one BSSID, double beacon rate, a second sequence counter).</li>\n      <li><b>Detection is not prevention, and I have no clean evasion run.</b> The Watcher proves a twin is detectable; it does not un-join a victim who already fell, and the kill only works on an unprotected board. The one attempt to evade the config tells (vendor IE) crashed the twin\'s beacon, so "the clock detectors are unevadable" stays an argument plus a device-independent measurement, not a head-to-head.</li>')

# Fix 6 (the one contribution): replace the conclusion closing line
sub('<p class="big" style="margin-top:10px">Attack and defence in one gadget: <span class="struct">built, measured on real hardware, and honestly bounded.</span></p>',
    '<p class="big" style="margin-top:10px"><span class="struct">The one contribution:</span> an on-device, measured comparison of evil-twin detectors, including the exact-BSSID clone the naive rule misses. Known methods, honestly replicated and run live on a $5 board.</p>')

P.write_text(h, encoding="utf-8")
print("patched", P.name)
