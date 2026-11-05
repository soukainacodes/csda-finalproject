#!/usr/bin/env python3
"""Add the measured protected-environment section (2 slides) after the CVE table."""
import sys
from pathlib import Path
P = Path(sys.argv[1]); h = P.read_text(encoding="utf-8")

slides = '''<!-- 16b PROTECTED-ENV measured -->
<section class="slide" data-sec="5 &middot; Microcontrollers">
  <h1>The twin's silicon is wide open, measured, not assumed</h1>
  <div class="body">
    <p class="lead">Read-only probing of my own two boards (no eFuses burned). Every hardware protection is off, on <em>both</em>, and the authenticated kill is the only guard.</p>
    <table style="max-width:1130px">
      <thead><tr class="toprule midrule"><th>Protection</th><th>What it stops</th><th>Twin</th><th>Watcher</th><th>Measured consequence</th></tr></thead>
      <tbody>
        <tr><td>Flash encryption</td><td>reading flash secrets</td><td class="yes">off</td><td class="yes">off</td><td>dump recovered the password + kill token</td></tr>
        <tr><td>Secure Boot v2</td><td>unsigned / OTA firmware</td><td class="yes">off</td><td class="yes">off</td><td>any reflash accepted</td></tr>
        <tr><td>JTAG / debug lock</td><td>debugger memory read</td><td class="yes">off</td><td class="yes">off</td><td>debug port open</td></tr>
        <tr class="botrule"><td>Kill-token auth <span style="color:var(--muted)">(software)</span></td><td>unauthenticated takedown</td><td class="no">on</td><td>n/a</td><td>wrong token rejected (KILL_ERR)</td></tr>
      </tbody>
      <caption>Table 4. espefuse / esptool on both ESP32-S3 boards. Raw: experiments/protected-env/. The one protection present (kill auth) is undermined: the token sits in the plaintext flash the dump reads.</caption>
    </table>
    <p class="lead" style="font-size:19px;margin-top:4px">A 4&nbsp;MB flash dump in 97&nbsp;s returned <span class="mono">Kaffi_Fr&iacute;</span>, <span class="mono alert">bestcoffee</span>, and the kill token <span class="mono alert">ghoul-begone-2026</span>, in the clear.</p>
  </div>
</section>

<!-- 16c PROTECTED-ENV cuts both ways -->
<section class="slide" data-sec="5 &middot; Microcontrollers">
  <h1>Protection cuts both ways</h1>
  <div class="body two" style="flex-direction:row">
    <div class="c">
      <p class="big struct" style="font-size:20px;margin-bottom:4px">A hardened twin resists the takedown</p>
      <ul class="sub">
        <li><b>Flash encryption</b> &mdash; the dump returns ciphertext; no password, no token.</li>
        <li><b>Secure Boot + signed OTA + anti-rollback</b> &mdash; an unsigned kill image or malicious OTA is <b>rejected</b>.</li>
        <li><b>JTAG lock</b> &mdash; no debugger memory read.</li>
        <li><b>The chain</b> &mdash; authenticating the kill is pointless if the token sits in plaintext flash.</li>
      </ul>
    </div>
    <div class="c">
      <p class="big struct" style="font-size:20px;margin-bottom:4px">So the same hardening shields a rogue</p>
      <ul class="sub">
        <li>The protections that secure honest IoT would also stop <em>me</em> from neutralising a well-built twin.</li>
        <li>Against a hardened rogue, <b>hacking back fails.</b></li>
        <li>What is left: <b>detection</b> (the Watcher) and <b>physical response</b>, locate by signal, unplug.</li>
        <li>Real devices keep failing here: Mirai, BrakTooth, fault-injection key recovery.</li>
      </ul>
    </div>
  </div>
</section>

'''

anchor = "<!-- 17 DISCUSSION: what defends -->"
assert h.count(anchor) == 1, "discussion anchor not found/unique"
h = h.replace(anchor, slides + anchor, 1)
P.write_text(h, encoding="utf-8")
print("patched", P.name, "| slides:", h.count('class="slide"'))
