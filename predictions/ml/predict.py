"""
predictions/ml/predict.py
--------------------------
Bridges the offline-trained model (predictions/ml/train.py,
model_registry/*.pkl) to live data captured through the Sensor Data module
(Prompt 4's `sensors.models.SensorReading`).

The model was trained on 4 sensor types: temperature, vibration, pressure,
rpm (see preprocessing.py). Real machines register their sensors with
free-text names (e.g. "Bearing Temperature", "Motor Vibration"), so
`_match_sensor()` maps each machine's SensorDefinitions to the model's
expected sensor keys via simple keyword matching. This is a deliberate,
documented approximation — see the design note in `get_feature_vector()`.
"""

from pathlib import Path

import joblib
import numpy as np

from sensors.models import SensorReading

from .preprocessing import FEATURE_COLUMNS, ROLLING_WINDOW, SENSOR_COLUMNS

MODEL_REGISTRY_DIR = Path(__file__).resolve().parent / "model_registry"

# Keyword -> model sensor key. Matching is case-insensitive substring match
# against each machine's SensorDefinition.sensor_name.
SENSOR_KEYWORD_MAP = {
    "temperature": "temperature",
    "temp": "temperature",
    "vibration": "vibration",
    "vib": "vibration",
    "pressure": "pressure",
    "rpm": "rpm",
    "speed": "rpm",
}

# Simple in-process cache so every prediction request doesn't re-read the
# .pkl from disk. Keyed by file path + modification time, so if train.py
# saves a new model the next prediction picks it up automatically without
# needing a server restart.
_model_cache = {}


class PredictionError(Exception):
    """
    Raised for any problem that prevents a prediction from being computed
    (missing model, missing sensors, insufficient history, bad data).
    Views catch this and show the message directly to the user rather than
    letting a stack trace surface — every failure mode here is something
    the user can actually act on (e.g. "add more readings", "define a
    vibration sensor").
    """


def _match_sensor(sensor_name: str):
    name = sensor_name.strip().lower()
    for keyword, model_key in SENSOR_KEYWORD_MAP.items():
        if keyword in name:
            return model_key
    return None


def load_active_model_version():
    """Returns the active ModelVersion row, or raises PredictionError."""
    # Imported here (not at module level) to avoid a circular import: this
    # module is imported by predictions/models.py's app config indirectly
    # via views, and predictions.models needs to already be loaded.
    from predictions.models import ModelVersion

    model_version = ModelVersion.objects.filter(is_active=True).first()
    if model_version is None:
        raise PredictionError(
            "No active prediction model is configured. Ask an Admin to run "
            "the training script and activate a model version."
        )
    return model_version


def load_model(model_version):
    """Loads (and caches) the joblib model file for a given ModelVersion."""
    # os.path.basename() strips any directory components — model_version
    # is Admin-controlled, not user-uploaded, so this is defense-in-depth
    # rather than a response to a demonstrated attack vector.
    import os
    safe_filename = os.path.basename(model_version.file_path)
    model_path = MODEL_REGISTRY_DIR / safe_filename

    if not model_path.exists():
        raise PredictionError(
            f"Model file '{model_version.file_path}' was not found on disk. "
            f"It may have been moved or deleted — retrain or restore it."
        )

    cache_key = str(model_path)
    mtime = model_path.stat().st_mtime
    cached = _model_cache.get(cache_key)
    if cached and cached["mtime"] == mtime:
        return cached["model"]

    try:
        model = joblib.load(model_path)
    except Exception as exc:  # noqa: BLE001 - surfaced directly to the user
        raise PredictionError(f"Could not load model file: {exc}")

    _model_cache[cache_key] = {"model": model, "mtime": mtime}
    return model


def get_feature_vector(machine):
    """
    Builds one feature row for `machine`, in the exact column order the
    model expects (FEATURE_COLUMNS), from its real recent SensorReading
    history.

    DESIGN NOTE — "cycle" feature approximation:
    The model was trained on simulated equipment where "cycle" is a
    sequential operating-cycle counter (0 to ~250). Real machines don't
    have this exact concept yet, so as an interim approximation we use the
    machine's total number of recorded readings as a stand-in "usage"
    signal. This is a reasonable proxy but not equivalent to the training
    data's scale — flagged here so whoever retrains the model on real
    historical data knows to revisit this mapping (e.g. using actual
    elapsed operating hours instead).

    Raises PredictionError if:
      - the machine has no sensor definitions matching a required model
        feature (temperature/vibration/pressure/rpm)
      - a matched sensor doesn't have enough reading history to compute
        the rolling-window features (needs at least ROLLING_WINDOW readings)
    """
    from sensors.models import SensorDefinition

    definitions = SensorDefinition.objects.filter(machine=machine, is_active=True)

    matched = {}
    for definition in definitions:
        model_key = _match_sensor(definition.sensor_name)
        if model_key and model_key not in matched:
            matched[model_key] = definition

    missing = [key for key in SENSOR_COLUMNS if key not in matched]
    if missing:
        raise PredictionError(
            f"'{machine.name}' is missing a required sensor for: {', '.join(missing)}. "
            f"Add a sensor definition whose name contains one of these keywords "
            f"so predictions can be computed: "
            + ", ".join(sorted({k for k, v in SENSOR_KEYWORD_MAP.items() if v in missing}))
        )

    features = {}
    total_reading_count = 0

    for model_key in SENSOR_COLUMNS:
        definition = matched[model_key]
        readings = list(
            SensorReading.objects.filter(sensor=definition).order_by("-recorded_at")[:ROLLING_WINDOW]
        )
        readings.reverse()  # oldest -> newest, matching training-time ordering

        if len(readings) < ROLLING_WINDOW:
            raise PredictionError(
                f"Not enough history for '{definition.sensor_name}' on '{machine.name}': "
                f"found {len(readings)} reading(s), need at least {ROLLING_WINDOW}. "
                f"Add more readings (manual entry or CSV/Excel upload) before predicting."
            )

        values = np.array([r.value for r in readings], dtype=float)
        total_reading_count = max(total_reading_count, SensorReading.objects.filter(sensor=definition).count())

        features[model_key] = values[-1]
        features[f"{model_key}_roll_mean"] = values.mean()
        features[f"{model_key}_roll_std"] = values.std(ddof=0) if len(values) > 1 else 0.0
        features[f"{model_key}_rate_of_change"] = values[-1] - values[-2]

    features["cycle"] = total_reading_count

    # Built as a single-row DataFrame (not a plain list) so column names
    # match what the model was trained on exactly — this avoids relying on
    # list positional order matching FEATURE_COLUMNS, and avoids sklearn's
    # "X does not have valid feature names" warning since the model was
    # fitted on a DataFrame during training.
    import pandas as pd
    row_df = pd.DataFrame([[features[col] for col in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
    return row_df, features


def predict_for_machine(machine, user=None):
    """
    Full pipeline: load active model -> build feature vector from real
    sensor history -> predict -> save a Prediction row -> return it.

    This is the single function views.py calls; it either returns a saved
    Prediction instance or raises PredictionError with a message safe to
    show directly to the user.
    """
    from predictions.models import Prediction, risk_level_for_probability

    model_version = load_active_model_version()
    model = load_model(model_version)
    row_df, feature_dict = get_feature_vector(machine)

    try:
        probability = float(model.predict_proba(row_df)[0][1])
    except Exception as exc:  # noqa: BLE001
        raise PredictionError(f"The model failed to produce a prediction: {exc}")

    risk_level = risk_level_for_probability(probability)

    prediction = Prediction.objects.create(
        machine=machine,
        model_version=model_version,
        failure_probability=round(probability, 4),
        risk_level=risk_level,
        input_snapshot=feature_dict,
        requested_by=user,
    )
    return prediction
