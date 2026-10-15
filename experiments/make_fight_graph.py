import csv, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

CSV = "round-logs/armsrace-synth-20261001-172013.csv"
rounds, deployed, retrained = [], [], []
with open(CSV) as f:
    for r in csv.DictReader(f):
        rounds.append(int(r["round"]))
        deployed.append(float(r["deployed_accuracy"]) if r["deployed_accuracy"] else None)
        retrained.append(float(r["accuracy"]))

SAND="#f3e7cf"; INK="#2b2118"; GOLD="#c8962d"; CRIMSON="#9e2b25"; DUNE="#d9c08a"
fig, ax = plt.subplots(figsize=(11,6.2))
fig.patch.set_facecolor(SAND); ax.set_facecolor("#faf4e6")

# shade rounds where the deployed detector was beaten (attacker ahead)
for rd, d in zip(rounds, deployed):
    if d is not None and d < 0.99:
        ax.axvspan(rd-0.5, rd+0.5, color=CRIMSON, alpha=0.10, zorder=0)

# retrained (the Watcher always comes back)
ax.plot(rounds, retrained, "--", color=GOLD, lw=2.5, marker="s", ms=7,
        label="After the Watcher retrains (it recovers)")
# deployed battle line (starts round 1; round 0 has no prior model)
xs=[r for r,d in zip(rounds,deployed) if d is not None]
ys=[d for d in deployed if d is not None]
ax.plot(xs, ys, color=INK, lw=2.5, marker="o", ms=8,
        label="Deployed detector vs the NEW disguise (dips = attacker evades)")
for x,y in zip(xs,ys):
    if y<0.99: ax.plot(x,y,"o",ms=13,mfc="none",mec=CRIMSON,mew=2.2,zorder=5)

ax.annotate("attacker finds a new disguise\nthe deployed detector is fooled",
            xy=(1,0.5), xytext=(2.4,0.34), color=CRIMSON, fontsize=10, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=1.6))
ax.annotate("Watcher retrains\nand catches it again",
            xy=(2,1.0), xytext=(2.6,0.70), color=GOLD, fontsize=10, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=GOLD, lw=1.6))
ax.annotate("a genuinely new trick (new BSSID scheme)\nkeeps the deployed detector down for several rounds",
            xy=(12,0.5), xytext=(6.6,0.20), color=CRIMSON, fontsize=9.5, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=1.6))

ax.set_ylim(0.10,1.06); ax.set_xlim(-0.4,13.4); ax.set_xticks(rounds)
ax.set_xlabel("Arms-race round  (each round the attacker changes its disguise)", fontsize=11)
ax.set_ylabel("Detection accuracy", fontsize=11)
ax.set_title("AL-GHUL vs the Watcher  —  the arms race",
             fontsize=16, fontweight="bold", color=INK)
ax.text(0.5,-0.155,"The attacker evades (black line dips), the Watcher retrains and recovers (gold). "
        "Shaded = rounds the attacker was ahead.",
        transform=ax.transAxes, ha="center", fontsize=9.5, style="italic", color="#5b4a33")
ax.grid(alpha=0.25); ax.legend(loc="lower center", fontsize=10, framealpha=0.95)
fig.tight_layout(rect=[0,0.02,1,1])
out="plots/fighting-graph.png"; fig.savefig(out, dpi=140, facecolor=SAND); print("saved", out)
