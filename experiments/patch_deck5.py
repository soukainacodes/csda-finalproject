#!/usr/bin/env python3
"""Append a closing QR slide to the deck (reproduce / repo link)."""
import sys
from pathlib import Path
P = Path(sys.argv[1]); h = P.read_text(encoding="utf-8")

qr = '''<!-- QR REPRODUCE -->
<section class="slide cover" data-nohf="1">
  <div class="inst">All code, logs and figures, open and reproducible</div>
  <h1 class="big-title" style="font-size:46px">Reproduce the whole thing</h1>
  <div class="rule"></div>
  <figure style="margin:8px 0 0"><img src="__FIG_QR__" alt="repository QR" style="width:250px;height:250px"></figure>
  <p class="sub" style="font-size:22px;font-family:var(--mono);margin-top:14px">github.com/soukainacodes/csda-finalproject</p>
  <div class="by"><span class="nm">Soukaina Mahboub Mehboub</span></div>
</section>

'''

anchor = "\n</div>\n<script>"
assert h.count(anchor) == 1, "deck-close anchor not unique"
h = h.replace(anchor, "\n" + qr + "</div>\n<script>", 1)
P.write_text(h, encoding="utf-8")
print("patched", P.name, "| slides:", h.count('class="slide"'), "| token:", h.count('__FIG_QR__'))
