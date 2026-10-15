"""Train the Watcher classifier from captured (or synthetic) records."""
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from .features import records_to_frame
from .evaluate import compute_metrics


def train_from_records(records, real_bssid, target_ssid=None, save_path=None,
                       n_estimators=200, random_state=0):
    """Returns (model, metrics, (X, y)). Metrics are on a held-out split when
    both classes are present, otherwise on the full set."""
    X, y, _groups = records_to_frame(records, real_bssid, target_ssid)
    if X.empty:
        raise ValueError("no usable frames to train on")

    clf = RandomForestClassifier(n_estimators=n_estimators,
                                 random_state=random_state, n_jobs=-1)

    if len(set(y)) < 2:
        # Only one class seen so far: fit on everything, metrics are degenerate.
        clf.fit(X, y)
        metrics = compute_metrics(clf, X, y)
    else:
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.3, random_state=random_state, stratify=y)
        clf.fit(X_tr, y_tr)
        metrics = compute_metrics(clf, X_te, y_te)

    if save_path:
        joblib.dump({"model": clf, "columns": list(X.columns)}, save_path)
    return clf, metrics, (X, y)


def load_model(path):
    bundle = joblib.load(path)
    return bundle["model"], bundle["columns"]
