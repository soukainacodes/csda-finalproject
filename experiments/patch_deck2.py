#!/usr/bin/env python3
"""Add the honest real-data ML slide to AL-GHUL-Slides-Academic-v2.html, and
update the limits bullet. Keyed on comment markers so images stay intact."""
import sys
from pathlib import Path

P = Path(sys.argv[1])
h = P.read_text(encoding="utf-8")

ml_slide = '''<!-- 9b RESULTS ML real -->
<section class="slide" data-sec="4 &middot; Results">
  <h1>A detector learned from the real captures confirms the physics</h1>
  <div class="body two" style="flex-direction:row">
    <div class="c" style="flex:0 0 46%">
      <p class="lead">I retrained the classifier the honest way: on the <b>real</b> beacons, with <b>no BSSID or MAC</b> as a feature (the leaks that sank the first attempt).</p>
      <ul class="it" style="margin-top:4px">
        <li>100% separation, zero false positives, but with two radios this is <b>separability, not generalization</b>. Said plainly, not a triumph.</li>
        <li>Its top features are <b>clock-skew, the IE fingerprint and beacon timing</b>, the same tells the hand detectors use, chosen independently.</li>
        <li>A clock/timing-only model, trained on the two-BSSID case, still flags <b>78%</b> of the <em>unseen</em> exact-clone beacons.</li>
      </ul>
      <p class="src">Source: experiments/ml_real.py; ml-real-results.md, on the watcher-onboard captures.</p>
    </div>
    <div class="c">
      <figure>
        <img src="__FIG_ML__" alt="RandomForest feature importances on real data">
        <figcaption>Figure 8. Feature importances of a RandomForest trained on the real captures. It ranks clock-skew (w_skew_ppm), the IE fingerprint (has70, n_vendors, n_ies, n221) and inter-beacon timing highest, the physical signals, not any identity field.</figcaption>
      </figure>
    </div>
  </div>
</section>

'''

# insert after the arms-race slide (before H5)
anchor = "<!-- 10 RESULTS H5 matrix -->"
assert h.count(anchor) == 1, "H5 anchor not unique"
h = h.replace(anchor, ml_slide + anchor, 1)

# update the limits ML bullet to reflect both the flat arms race and the real-data result
old = '<li><b>The ML leg is a framework, not a result.</b> Synthetic separation, a flat arms-race curve, and label leakage mean it is not validated as a detector.</li>'
new = '<li><b>The ML is honestly bounded.</b> The arms-race curve stayed flat (a framework, not an evasion result), and the real-data classifier separates twin from real across only two radios, so it is a separability and corroboration result, not proof of generalization.</li>'
assert h.count(old) == 1, "limits ML bullet not found"
h = h.replace(old, new, 1)

P.write_text(h, encoding="utf-8")
print("patched", P.name, "| slides:", h.count('class="slide"'), "| FIG_ML token:", h.count('__FIG_ML__'))
