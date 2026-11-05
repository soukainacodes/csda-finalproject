#!/usr/bin/env python3
"""Generate the two academic figures for the slide deck, from measured data.

  fig_clockskew.png : per-BSSID TSF clock fit error (RMSE), log scale. Genuine
                      single clocks sit at 13-79 us; the exact-BSSID clone (two
                      clocks mixed) explodes to 7.3e10 us. Any threshold between
                      separates perfectly. Source: watcher-summary-{A,B,C}-*.json.
  fig_timing.png    : on-board detection over the 150 s exact-clone run, detected
                      bands vs clear gaps, ~83% coverage, first detect ~6 s.
                      Source: watcher-onboard-sum-Btiming-20261105-125305.json.

Academic style: serif, thin spines, restrained blue/red, no gradients or chrome.
"""
import json, glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "plots"; OUT.mkdir(exist_ok=True)


def _rmse(scn, bssid, fallback):
    """Load a per-BSSID clock-fit RMSE from the watcher-summary log (not hardcoded)."""
    for f in reversed(sorted(glob.glob(str(HERE / f"watcher-summary-{scn}-*.json")))):
        cs = json.load(open(f)).get("clock_skew", {})
        if bssid in cs and cs[bssid].get("fit_rmse_us") is not None:
            return cs[bssid]["fit_rmse_us"]
    return fallback


def _bands(fallback):
    """Load the DETECTED time bands from the Btiming on-board log (not hardcoded)."""
    fs = sorted(glob.glob(str(HERE / "watcher-onboard-sum-Btiming-*.json")))
    if not fs:
        return fallback
    tr = json.load(open(fs[-1])).get("transitions", [])
    bands, start = [], None
    for t in tr:
        if t["state"] == "DETECTED":
            start = t["t"]
        elif t["state"] == "CLEAR" and start is not None:
            bands.append((start, t["t"])); start = None
    return bands or fallback

INK = "#161616"; STRUCT = "#23237a"; ALERT = "#9a1420"; MUTED = "#5a5a5a"
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["CMU Serif", "DejaVu Serif", "Times New Roman"],
    "mathtext.fontset": "cm",
    "axes.edgecolor": INK, "axes.linewidth": 0.9,
    "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK,
    "figure.dpi": 150,
})

# ---- Figure 1: clock-skew separation ----------------------------------------
labels = ["single AP\n(scn C)", "twin, own id\n(scn A)", "real AP\n(scn A)", "cloned id\n(scn B)"]
rmse   = [_rmse("C", "aa:d0:43:06:46:e1", 13.0), _rmse("A", "02:a1:00:00:00:01", 24.0),
          _rmse("A", "aa:d0:43:06:46:e1", 79.0), _rmse("B", "aa:d0:43:06:46:e1", 72617788294.5)]
colors = [STRUCT, STRUCT, STRUCT, ALERT]

fig, ax = plt.subplots(figsize=(5.4, 3.5))
bars = ax.bar(range(4), rmse, color=colors, width=0.62, zorder=3)
ax.set_yscale("log")
ax.set_ylim(1, 1e12)
ax.set_ylabel("single-line TSF fit error  (microseconds, log)", fontsize=10)
ax.set_xticks(range(4)); ax.set_xticklabels(labels, fontsize=9.5)
ax.axhline(1e3, ls="--", lw=1.0, color=MUTED, zorder=2)
ax.text(3.42, 1.6e3, "any threshold here\nseparates perfectly", fontsize=8.5,
        color=MUTED, style="italic", ha="right", va="bottom")
for i, v in enumerate(rmse):
    txt = f"{v:.0f}" if v < 1e4 else f"{v:.1e}"
    ax.text(i, v * (2.1 if v < 1e4 else 2.3), txt, ha="center", va="bottom",
            fontsize=9, color=(ALERT if i == 3 else INK))
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.tick_params(length=3)
fig.tight_layout()
fig.savefig(OUT / "fig_clockskew.png", bbox_inches="tight", facecolor="white")
plt.close(fig)

# ---- Figure 2: on-board detection timeline (exact clone, 150 s) --------------
# transitions from watcher-onboard-sum-Btiming-20261105-125305.json
det = _bands([(6.1, 47.1), (49.1, 86.1), (93.1, 140.1)])   # DETECTED bands, loaded from the Btiming log
fig, ax = plt.subplots(figsize=(6.6, 2.1))
for a, b in det:
    ax.axvspan(a, b, ymin=0.30, ymax=0.78, color=STRUCT, alpha=0.82, zorder=3)
ax.axvspan(0, 0, color=STRUCT, alpha=0.82, label="detected (red LED)")
ax.set_xlim(0, 150); ax.set_ylim(0, 1)
ax.set_yticks([])
ax.set_xlabel("time since capture start  (s)", fontsize=10)
for x in (6.1, 49.1, 93.1):
    ax.annotate("", xy=(x, 0.80), xytext=(x, 0.95),
                arrowprops=dict(arrowstyle="-|>", color=ALERT, lw=1.0))
ax.text(6.1, 0.97, "first detect 6.1 s", fontsize=8.5, color=ALERT, va="bottom", ha="left")
ax.text(75, 0.13, "detected ~125 s of 150 s  (~83%);  gaps 2 s and 7 s;  clears ~8 s after a radio leaves",
        fontsize=8.5, color=MUTED, style="italic", ha="center")
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.tick_params(length=3)
fig.tight_layout()
fig.savefig(OUT / "fig_timing.png", bbox_inches="tight", facecolor="white")
plt.close(fig)

print("wrote", OUT / "fig_clockskew.png")
print("wrote", OUT / "fig_timing.png")
