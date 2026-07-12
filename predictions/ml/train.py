"""
predictions/ml/train.py
------------------------
Trains the predictive-maintenance classifier and saves it for the Django
app to load at prediction time (predictions/ml/predict.py, built in a
later prompt, will do: `joblib.load(...)` + `.predict_proba()`).

Run manually (or via a Django management command later) whenever the model
needs retraining — this deliberately does NOT run inside a web request,
since training is comparatively slow and shouldn't block a page load
(see the Development Roadmap / design decisions in Prompt 1).

Usage:
    python predictions/ml/train.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import sklearn
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

# Allow running this file directly (`python train.py`) as well as as a
# module (`python -m predictions.ml.train`).
sys.path.append(str(Path(__file__).resolve().parent))
try:
    from preprocessing import FEATURE_COLUMNS, build_dataset, split_train_test
except ImportError:
    from predictions.ml.preprocessing import FEATURE_COLUMNS, build_dataset, split_train_test

MODEL_REGISTRY_DIR = Path(__file__).resolve().parent / "model_registry"
MODEL_REGISTRY_DIR.mkdir(exist_ok=True)


def evaluate(name, model, X_test, y_test):
    """
    Computes the four standard classification metrics plus a confusion
    matrix for one trained model, and prints a readable summary.

    Metric choices, and why all four (not just accuracy) matter here:
      - Accuracy   : overall % of correct predictions. Can be misleading
                     on imbalanced data (e.g. if only 15% of readings are
                     "needs maintenance", a model that always predicts
                     "healthy" would score 85% accuracy while being
                     completely useless).
      - Precision  : of the readings the model FLAGGED as needing
                     maintenance, what fraction actually did? Low precision
                     means too many false alarms (wasted maintenance trips).
      - Recall     : of the readings that ACTUALLY needed maintenance, what
                     fraction did the model catch? Low recall means missed
                     failures — the costlier mistake in this domain, since
                     an unplanned breakdown is far more expensive than an
                     unnecessary inspection.
      - F1 Score   : the harmonic mean of precision and recall — a single
                     number balancing both, useful for comparing models
                     when neither precision nor recall alone tells the
                     full story.
      - Confusion Matrix : the raw breakdown of True Negative / False
                     Positive / False Negative / True Positive counts that
                     precision/recall/F1 are computed from — shown so the
                     actual error pattern (e.g. "mostly false alarms" vs.
                     "mostly missed failures") is visible, not just a
                     single summary number.
    """
    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1_score": round(f1_score(y_test, y_pred, zero_division=0), 4),
    }
    cm = confusion_matrix(y_test, y_pred).tolist()

    print(f"\n--- {name} ---")
    print(f"Accuracy : {metrics['accuracy']}")
    print(f"Precision: {metrics['precision']}")
    print(f"Recall   : {metrics['recall']}")
    print(f"F1 Score : {metrics['f1_score']}")
    print("Confusion Matrix (rows=actual, cols=predicted, order=[0,1]):")
    print(f"  {cm}")

    return metrics, cm


def main():
    print("=" * 70)
    print("STEP 1-4: Building dataset (generate -> label -> engineer -> clean)")
    print("=" * 70)
    df = build_dataset()
    print(f"Dataset ready: {len(df)} rows, {df['unit_id'].nunique()} machines, "
          f"{df['needs_maintenance'].mean():.1%} positive (needs maintenance) rate.")

    print("\n" + "=" * 70)
    print("STEP 5: Train/test split (grouped by machine, 80/20)")
    print("=" * 70)
    X_train, X_test, y_train, y_test = split_train_test(df)
    print(f"Train rows: {len(X_train)} | Test rows: {len(X_test)}")

    print("\n" + "=" * 70)
    print("STEP 6: Training models")
    print("=" * 70)

    # Decision Tree: trained first as the simpler baseline. A single tree
    # is fast and interpretable but prone to overfitting the training data
    # (it can grow branches that memorize noise rather than genuine
    # patterns), which typically shows up as a bigger gap between how it
    # performs on training data vs. this held-out test set.
    dt_model = DecisionTreeClassifier(max_depth=10, class_weight="balanced", random_state=42)
    dt_model.fit(X_train, y_train)

    # Random Forest: an ensemble of many decision trees (each trained on a
    # bootstrapped sample with a random subset of features per split), with
    # predictions averaged across all trees. This reduces the overfitting
    # any single tree is prone to and generally gives more stable, better-
    # generalizing predictions — which is why it's the primary model.
    rf_model = RandomForestClassifier(
        n_estimators=200, max_depth=12, class_weight="balanced", random_state=42, n_jobs=-1,
    )
    rf_model.fit(X_train, y_train)

    print("\n" + "=" * 70)
    print("STEP 7: Evaluation (Accuracy / Precision / Recall / F1 / Confusion Matrix)")
    print("=" * 70)
    dt_metrics, dt_cm = evaluate("Decision Tree", dt_model, X_test, y_test)
    rf_metrics, rf_cm = evaluate("Random Forest", rf_model, X_test, y_test)

    print("\n--- Comparison ---")
    print(f"{'Metric':<12}{'Decision Tree':<16}{'Random Forest':<16}")
    for key in ["accuracy", "precision", "recall", "f1_score"]:
        print(f"{key:<12}{dt_metrics[key]:<16}{rf_metrics[key]:<16}")

    # Random Forest is selected as the deployed model whenever it matches
    # or beats the Decision Tree on F1 (the balanced precision/recall
    # metric) — which is expected given it's an ensemble of trees like the
    # baseline. The comparison is still trained and reported every run so
    # that choice is justified by evidence rather than assumed.
    chosen_name = "RandomForestClassifier" if rf_metrics["f1_score"] >= dt_metrics["f1_score"] else "DecisionTreeClassifier"
    chosen_model = rf_model if chosen_name == "RandomForestClassifier" else dt_model
    chosen_metrics = rf_metrics if chosen_name == "RandomForestClassifier" else dt_metrics
    chosen_cm = rf_cm if chosen_name == "RandomForestClassifier" else dt_cm
    print(f"\nSelected for deployment: {chosen_name} (higher/equal F1 score)")

    print("\n" + "=" * 70)
    print("STEP 8: Feature importance (Random Forest)")
    print("=" * 70)
    importances = sorted(
        zip(FEATURE_COLUMNS, rf_model.feature_importances_), key=lambda x: x[1], reverse=True
    )
    for feature, importance in importances[:8]:
        print(f"  {feature:<28} {importance:.4f}")

    print("\n" + "=" * 70)
    print("STEP 9: Saving model with joblib")
    print("=" * 70)
    version_name = "v1"
    model_path = MODEL_REGISTRY_DIR / f"model_{version_name}.pkl"
    joblib.dump(chosen_model, model_path)

    metadata = {
        "version_name": version_name,
        "algorithm": chosen_name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sklearn_version": sklearn.__version__,
        "feature_columns": FEATURE_COLUMNS,
        "metrics": chosen_metrics,
        "confusion_matrix": chosen_cm,
        "comparison": {
            "decision_tree": dt_metrics,
            "random_forest": rf_metrics,
        },
        "is_active": True,
    }
    metadata_path = MODEL_REGISTRY_DIR / f"model_{version_name}_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Model saved to:    {model_path}")
    print(f"Metadata saved to: {metadata_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
