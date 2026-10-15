"""End-to-end validation of the Watcher pipeline on synthetic data (no hardware).

Run from the watcher/ directory:
    python -m pytest -q
or directly:
    python tests/test_pipeline.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.armsrace import SynthBackend, run          # noqa: E402
from src.synth import generate_round, default_genome # noqa: E402
from src.features import records_to_frame            # noqa: E402
from src.train import train_from_records             # noqa: E402
from src.evaluate import compute_metrics            # noqa: E402


def test_features_and_training():
    recs = generate_round(default_genome(), 120, "LabNet",
                          "3c:aa:bb:cc:dd:01", "02:a1:00:00:00:01", seed=1)
    X, y, groups = records_to_frame(recs, "3c:aa:bb:cc:dd:01", "LabNet")
    assert not X.empty
    assert set(y) == {0, 1}
    model, metrics, _ = train_from_records(recs, "3c:aa:bb:cc:dd:01", "LabNet")
    # the round-0 disguise is obvious, so the Watcher should catch it easily
    assert metrics["accuracy"] > 0.8
    assert 0.0 <= metrics["fpr"] <= 1.0


def test_armsrace_curve():
    history = run(SynthBackend(n_each=120), rounds=6)
    assert len(history) == 6
    for h in history:
        assert 0.0 <= float(h["fpr"]) <= 1.0
        assert 0.0 <= float(h["accuracy"]) <= 1.0
    # early round should detect the obvious twin well
    assert float(history[0]["accuracy"]) > 0.8
    print("arms-race curve (accuracy):", [h["accuracy"] for h in history])


if __name__ == "__main__":
    test_features_and_training()
    test_armsrace_curve()
    print("ALL TESTS PASSED")
