#!/usr/bin/env python3
"""Patch AL-GHUL-Slides-Academic-v2.html with this week's measured results.

Keyed on the slide comment markers so the embedded base64 images are untouched.
Swaps the ML-100% detection headline for the measured on-board physical detection,
adds the kill-chain + clock-skew + timing figures, demotes the ML honestly, and
fixes the conclusion/limits/contribution. Figure images go in as tokens, injected
later. No invented numbers: every figure is backed by a file in experiments/.
"""
import re, sys
from pathlib import Path

P = Path(sys.argv[1])
h = P.read_text(encoding="utf-8")


def repl_between(h, start, end, new):
    pat = re.compile(re.escape(start) + r".*?(?=" + re.escape(end) + r")", re.S)
    n = len(pat.findall(h))
    if n != 1:
        raise SystemExit(f"marker {start!r} matched {n} spans (need 1)")
    return pat.sub(lambda m: new, h, count=1)


# --- preserve the existing arms-race image from slide 9 ---
m = re.search(r'(<img src="data:image/png;base64,[^"]+" alt="detection accuracy across arms-race rounds">)', h)
arms_img = m.group(1) if m else '<img src="" alt="arms race">'

# ---- slide 5b: kill chain (new, inserted before hypotheses) ----
def box(x, y, w, hh, color, t1, t2):
    cx = x + w / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" fill="none" stroke="{color}" stroke-width="1.3"/>'
            f'<text x="{cx}" y="{y+26}" text-anchor="middle" font-family="var(--mono)" font-size="13" fill="{color}">{t1}</text>'
            f'<text x="{cx}" y="{y+45}" text-anchor="middle" font-family="var(--mono)" font-size="11.5" fill="#161616">{t2}</text>')

INK, RED, BLU = "#121212", "#9a1420", "#23237a"
xs = [10, 194, 378, 562, 746, 930]
titles = [("1 Recon", "sniff beacons"), ("2 Clone", "twin on air"), ("3 Silent roam", "stored creds"),
          ("4 Portal", "phishing"), ("5 Cookie", "2FA bypass"), ("6 Harvest", "DNS metadata")]
cols = [INK, RED, RED, INK, INK, INK]
boxes = "".join(box(x, 40, 160, 66, c, t1, t2) for x, (t1, t2), c in zip(xs, titles, cols))
arrows = "".join(f'<line x1="{x+160}" y1="73" x2="{x+184}" y2="73" stroke="#161616" stroke-width="1.1" marker-end="url(#k)"/>'
                 for x in xs[:-1])
watcher = (box(300, 212, 250, 66, BLU, "The Watcher (ESP32)", "detect from beacons, LED red")
           + '<line x1="425" y1="212" x2="425" y2="108" stroke="#23237a" stroke-width="1.2" marker-end="url(#k)"/>'
           + '<text x="455" y="165" font-family="var(--serif)" font-style="italic" font-size="14" fill="#23237a">catches the twin here,</text>'
           + '<text x="455" y="185" font-family="var(--serif)" font-style="italic" font-size="14" fill="#23237a">before stages 4&ndash;6</text>')

killchain = f'''<!-- 5b KILL CHAIN -->
<section class="slide" data-sec="3 &middot; System &amp; method">
  <h1>The kill chain, and where the defence breaks it</h1>
  <div class="body">
    <figure>
      <svg viewBox="0 0 1100 300" class="arch" xmlns="http://www.w3.org/2000/svg">
        <defs><marker id="k" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6" fill="none" stroke="#161616" stroke-width="1.1"/></marker></defs>
        {boxes}{arrows}{watcher}
      </svg>
      <figcaption>Figure 3. AL-GH&#362;L's attack chain, left to right. The Watcher intervenes at the clone stage, detecting the twin from its beacons in seconds, so the credential, cookie and harvest stages are pre-empted.</figcaption>
    </figure>
    <p class="lead" style="margin-top:2px">Catch the twin on the air, and every later stage falls away.</p>
  </div>
</section>

'''

# ---- slide 8 (H3a): exact clone vs physics + clock-skew figure ----
s8 = '''<!-- 8 RESULTS H3a exact clone -->
<section class="slide" data-sec="4 &middot; Results">
  <h1>H3: the exact clone defeats the naive rule, physics does not</h1>
  <div class="body two" style="flex-direction:row">
    <div class="c" style="flex:0 0 45%">
      <p class="lead">The cheap rule is "one name seen from two hardware ids (BSSID) = a twin." An attacker who clones the <b>exact</b> BSSID makes that rule go blind: the Watcher now sees a single id. What the twin cannot fake is a second <b>hardware clock</b>.</p>
      <ul class="it" style="margin-top:4px">
        <li><b>rule-1</b> (BSSID count) &mdash; <span class="alert">blind</span> to the exact clone.</li>
        <li><b>IE-fingerprint</b> &mdash; two capability sets under one id.</li>
        <li><b>clock-skew / TSF-jump</b> &mdash; two independent radio clocks under one id; not spoofable.</li>
      </ul>
      <p class="src">Source: experiments/master-detector-comparison.md; watcher-summary-{A,B,C}.</p>
    </div>
    <div class="c">
      <figure>
        <img src="__FIG_CLOCKSKEW__" alt="clock-skew fit error, genuine versus cloned">
        <figcaption>Figure 4. Fitting each access point's advertised clock (TSF) to real time. Genuine single clocks sit at 13&ndash;79&nbsp;&micro;s; the exact clone mixes two clocks under one id and the single-line fit explodes to 7.3&times;10<sup>10</sup>&nbsp;&micro;s. Any threshold between them separates perfectly.</figcaption>
      </figure>
    </div>
  </div>
</section>

<!-- 8b RESULTS H3b on-board live -->
<section class="slide" data-sec="4 &middot; Results">
  <h1>Caught live, on a second microcontroller</h1>
  <div class="body two" style="flex-direction:row">
    <div class="c" style="flex:0 0 45%">
      <p class="lead">The detectors run <b>on the board</b>: a second ESP32 sniffs beacons and lights its LED red. Measured across three ground-truth scenarios on my own hardware.</p>
      <table style="margin-top:4px">
        <thead><tr class="toprule midrule"><th>Scenario</th><th>rule-1</th><th>physical</th></tr></thead>
        <tbody>
          <tr><td>A &middot; twin, own id</td><td class="no">detect</td><td class="no">detect</td></tr>
          <tr><td>B &middot; exact clone</td><td class="yes">MISS</td><td class="no">detect</td></tr>
          <tr class="botrule"><td>C &middot; one AP (control)</td><td>clear</td><td>clear</td></tr>
        </tbody>
        <caption>Table 1. On-board verdict. Only the physical detectors catch the exact clone (B); neither false-alarms on a lone AP (C). Detection confirmed under WPA2 and WPA2+PMF.</caption>
      </table>
    </div>
    <div class="c">
      <figure>
        <img src="__FIG_TIMING__" alt="on-board detection over time">
        <figcaption>Figure 5. On-board detection of the exact clone over a 150&nbsp;s run: first detect ~6&nbsp;s, held ~83% of the time, clears ~8&nbsp;s after a radio leaves. Source: watcher-onboard-sum-Btiming; onboard-results-2026-11-05.md.</figcaption>
      </figure>
    </div>
  </div>
</section>

'''

# ---- slide 9 (H4): ML arms race demoted, keep existing figure ----
s9 = f'''<!-- 9 RESULTS H4 arms race -->
<section class="slide" data-sec="4 &middot; Results">
  <h1>H4: the AI-vs-AI arms race, and its honest limit</h1>
  <div class="body two" style="flex-direction:row">
    <div class="c" style="flex:0 0 45%">
      <p class="lead">I also built the contest the title promises: an evolutionary attacker that mutates its disguise against a machine-learning detector that retrains each round.</p>
      <ul class="it" style="margin-top:4px">
        <li>The framework runs end to end, in simulation and on hardware.</li>
        <li><span class="alert">But the curve stays flat.</span> The ESP32's disguise knobs are too coarse to truly evade, so no dip-and-recover appears in any hardware run.</li>
        <li>So I treat the ML leg as a <b>framework and a limitation</b>, and rest the detection findings on the measured physical detectors.</li>
      </ul>
      <p class="src">Source: experiments/ml-watcher-limitations.md; round-logs/armsrace-*.</p>
    </div>
    <div class="c">
      <figure>
        {arms_img}
        <figcaption>Figure 6. The arms-race framework (synthetic). The intended dip-and-recover did not occur on this hardware, so I report the ML leg as a limitation rather than a detection result.</figcaption>
      </figure>
    </div>
  </div>
</section>

'''

# ---- conclusion (fix ML-100% claim) ----
concl = '''<!-- 19 CONCLUSION -->
<section class="slide" data-sec="7 &middot; Conclusion">
  <h1>Conclusion</h1>
  <div class="body">
    <ul class="it">
      <li>The twin took the victim <b>silently, with no human action</b>, on every WPA2-family mode (H1, H2, H5).</li>
      <li>A second microcontroller detects the twin from its beacons alone, <b>live, on the board</b>, and catches even an <b>exact-BSSID clone</b> the naive count rule misses (H3), through the one tell the attacker cannot forge: a second hardware clock.</li>
      <li>The AI-vs-AI arms race ran as a <b>framework</b>; on this hardware the disguise space was too coarse to evade, so I report it as a limitation (H4).</li>
      <li>The real weakness is the <b>shared password</b>: personal modes prove knowledge, not identity. Only certificate-based identity truly refuses the twin.</li>
      <li>A microcontroller cannot secure itself; <b>its environment must</b>, with encryption, secure boot, and no hardcoded secrets.</li>
    </ul>
    <p class="big" style="margin-top:10px">Attack and defence in one gadget: <span class="struct">built, measured on real hardware, and honestly bounded.</span></p>
  </div>
</section>

'''

# ---- honest limits (add WPA3 capture, single-Watcher, ML) ----
limits = '''<!-- 18 HONEST LIMITS -->
<section class="slide" data-sec="6 &middot; Discussion">
  <h1>Honest limits: what I did not prove</h1>
  <div class="body">
    <ul class="it">
      <li><b>One Watcher, one real AP, one twin.</b> A legitimate enterprise network has many BSSIDs for one name, where the naive count rule would false-positive; that regime is untested, and the physical detectors still need validation against genuinely identical APs.</li>
      <li><b>WPA3 detection not measured.</b> In WPA3-SAE my twin did not beacon capturably on this ESP32, so detection under WPA3 is a gap, not a result. WPA2 and WPA2+PMF were confirmed.</li>
      <li><b>The ML leg is a framework, not a result.</b> Synthetic separation, a flat arms-race curve, and label leakage mean it is not validated as a detector.</li>
      <li><b>One victim device, 2.4&nbsp;GHz, a proxy roam.</b> Timings came from a single Samsung tablet; I triggered the capture by switching the real AP off. Own lab and devices only.</li>
    </ul>
    <p class="big" style="margin-top:8px">I corrected my own first assumption: <span class="alert">WPA3 / PMF does not kill the twin,</span> it only raises the cost by one tap the victim gives.</p>
  </div>
</section>

'''

# apply section swaps
h = repl_between(h, "<!-- 8 RESULTS H3 -->", "<!-- 9 RESULTS H4 arms race -->", s8)
h = repl_between(h, "<!-- 9 RESULTS H4 arms race -->", "<!-- 10 RESULTS H5 matrix -->", s9)
h = repl_between(h, "<!-- 18 HONEST LIMITS -->", "<!-- 19 CONCLUSION -->", limits)
h = repl_between(h, "<!-- 19 CONCLUSION -->", "<!-- 20 REFERENCES -->", concl)
# insert kill chain before hypotheses
h = h.replace("<!-- 6 HYPOTHESES + METHOD -->", killchain + "<!-- 6 HYPOTHESES + METHOD -->", 1)

# targeted small fixes
h = h.replace(
  '<li><b>The Watcher</b>, the defender: a machine-learning classifier that learns the twin\'s radio fingerprint and flags it. <span class="sub">The deployable contribution.</span></li>',
  '<li><b>The Watcher</b>, the defender: a second ESP32 that detects the twin from its beacons alone, live on the board, and catches even an exact-BSSID clone the naive rule misses. <span class="sub">The deployable contribution.</span></li>')
h = h.replace(
  '<li><b>H3 &mdash; detectability.</b> The Watcher separates twin from real AP with accuracy A and false-positive rate F, <em>without</em> using the BSSID as a feature.</li>',
  '<li><b>H3 &mdash; detectability.</b> The Watcher separates twin from real AP from beacons alone, including an <em>exact-BSSID clone</em> that a BSSID-count rule cannot see.</li>')
h = h.replace('RandomForest, laptop', 'on-board + laptop ML')
h = h.replace('Figure 4. Autonomous run', 'Figure 7. Autonomous run')
h = h.replace(
  '<p>[12] WiGLE.net network statistics, 2025; HPE Aruba / Juniper Mist telemetry, 2026.</p>',
  '<p>[12] WiGLE.net network statistics, 2025; HPE Aruba / Juniper Mist telemetry, 2026.</p>\n    <p>[13] S. Jana and S. K. Kasera. On fast and accurate detection of unauthorized Wi-Fi access points. <em>IEEE Trans. Mobile Computing</em>, 2010.</p>\n    <p>[14] F. Guo and T. Chiueh. Sequence number-based MAC address spoof detection. <em>RAID</em>, 2005.</p>')
h = h.replace('<p>[13] OWASP. Internet of Things Top 10 (I1: weak / hardcoded passwords).</p>',
              '<p>[15] OWASP. Internet of Things Top 10 (I1: weak / hardcoded passwords).</p>')

P.write_text(h, encoding="utf-8")
print("patched", P.name, "| slides:", h.count('class="slide"'))
