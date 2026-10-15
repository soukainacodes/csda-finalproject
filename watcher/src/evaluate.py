"""Metrics for the Watcher. The twin is the positive class (label 1)."""
from sklearn.metrics import (accuracy_score, precision_score,
                             recall_score, confusion_matrix)


def compute_metrics(model, X, y) -> dict:
    if X is None or len(X) == 0:
        return {"accuracy": 0, "precision": 0, "recall": 0, "fpr": 0,
                "tp": 0, "fp": 0, "fn": 0, "tn": 0, "n": 0}
    y_pred = model.predict(X)
    tn, fp, fn, tp = confusion_matrix(y, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {
        "accuracy": float(accuracy_score(y, y_pred)),
        "precision": float(precision_score(y, y_pred, zero_division=0)),
        "recall": float(recall_score(y, y_pred, zero_division=0)),
        "fpr": float(fpr),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "n": int(len(y)),
    }


def detection_rate(model, X) -> float:
    """Fraction of rows the model flags as twin. Used as the attacker's fitness
    signal (it wants this LOW on its own twin frames)."""
    if X is None or len(X) == 0:
        return 0.0
    return float(model.predict(X).mean())
