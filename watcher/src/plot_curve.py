"""Plot the arms-race curve (the H4 figure)."""
import csv


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def plot_from_history(history, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rounds = [int(h["round"]) for h in history]
    deployed = [_f(h.get("deployed_accuracy", "")) for h in history]
    retrained = [_f(h.get("accuracy", "")) for h in history]
    fpr = [_f(h.get("fpr", "")) for h in history]

    fig, ax = plt.subplots(figsize=(8, 5))
    # The arms-race headline: the deployed detector facing each NEW disguise.
    ax.plot(rounds, deployed, marker="o", linewidth=2,
            label="Deployed detector vs new disguise (dips = attacker evades)")
    # The recovery: accuracy after the Watcher retrains on the new disguise.
    ax.plot(rounds, retrained, marker="s", linestyle="--",
            label="Accuracy after retraining (Watcher recovers)")
    ax.plot(rounds, fpr, marker="^", alpha=0.6, label="False-positive rate")
    ax.set_xlabel("Arms-race round")
    ax.set_ylabel("Rate")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("AL-GHUL vs the Watcher: detection across rounds (H4)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def plot_from_csv(csv_path, out_png):
    with open(csv_path) as f:
        history = list(csv.DictReader(f))
    plot_from_history(history, out_png)
