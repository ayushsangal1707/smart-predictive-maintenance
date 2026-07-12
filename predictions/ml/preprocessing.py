"""
predictions/ml/preprocessing.py
--------------------------------
Data preparation for the predictive-maintenance classifier.

WHY SYNTHETIC DATA:
BHEL's real plant sensors aren't available during this internship, so this
module generates a realistic *synthetic run-to-failure dataset* to train
and validate the pipeline end-to-end. The generator simulates the same
shape of data the real system will eventually collect via the Sensor Data
module (Prompt 4): multiple machines, each producing periodic sensor
readings (temperature, vibration, pressure, RPM) that gradually degrade as
the machine approaches failure. This lets every later step (feature
engineering, model training, evaluation, saving) be built and proven
correct now, and swapped over to real `SensorReading` rows later by
replacing only `load_raw_data()` — nothing downstream needs to change.

THE LABELING APPROACH (binary classification):
Each simulated machine ("unit") runs for a random lifetime measured in
"cycles" (think: operating days) before it would fail if left unmaintained.
At every cycle we know the Remaining Useful Life (RUL) = lifetime - current
cycle. We label a row 1 ("needs maintenance soon") if RUL is within a
threshold window (default 20 cycles) of failure, and 0 otherwise. This is
the standard framing used in predictive-maintenance ML (the same idea
behind NASA's well-known CMAPSS turbofan degradation benchmark) — it turns
a hard regression problem (predict exact RUL) into an easier, more
actionable binary classification problem ("should we schedule maintenance
now or not?").
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

RANDOM_SEED = 42
RUL_FAILURE_THRESHOLD = 20  # cycles-to-failure considered "needs maintenance soon"
ROLLING_WINDOW = 5

SENSOR_COLUMNS = ["temperature", "vibration", "pressure", "rpm"]

FEATURE_COLUMNS = (
    SENSOR_COLUMNS
    + ["cycle"]
    + [f"{s}_roll_mean" for s in SENSOR_COLUMNS]
    + [f"{s}_roll_std" for s in SENSOR_COLUMNS]
    + [f"{s}_rate_of_change" for s in SENSOR_COLUMNS]
)

TARGET_COLUMN = "needs_maintenance"


# ---------------------------------------------------------------------------
# STEP 1: Data generation / loading
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n_units: int = 100, random_seed: int = RANDOM_SEED) -> pd.DataFrame:
    """
    Simulates run-to-failure histories for `n_units` machines.

    For each unit:
      - a random total lifetime is drawn (100-250 cycles)
      - at every cycle, sensor readings are generated from a baseline value
        that drifts (degrades) as the unit approaches its lifetime, plus
        random noise and a small per-unit random offset (so not all
        machines degrade identically — mirrors real equipment variability).

    Returns a long-format DataFrame: one row per (unit_id, cycle), matching
    the shape the real system will have once SensorReading rows are pivoted
    per-machine-per-timestamp.
    """
    rng = np.random.default_rng(random_seed)
    rows = []

    for unit_id in range(1, n_units + 1):
        lifetime = rng.integers(100, 250)

        # Per-unit random effect: some machines simply run a bit hotter /
        # noisier than others even when healthy — this is what makes the
        # classification problem non-trivial (a fixed threshold rule alone
        # would not perfectly separate healthy from at-risk).
        unit_offset = rng.normal(0, 1, size=len(SENSOR_COLUMNS))

        for cycle in range(lifetime):
            degradation = cycle / lifetime  # 0 (new) -> 1 (about to fail)

            temperature = 40 + unit_offset[0] + degradation * 25 + rng.normal(0, 2)
            vibration = 1.0 + unit_offset[1] * 0.3 + degradation * 4 + rng.normal(0, 0.3)
            pressure = 5.0 + unit_offset[2] * 0.2 - degradation * 1.5 + rng.normal(0, 0.2)
            rpm = 1500 + unit_offset[3] * 20 - degradation * 150 + rng.normal(0, 15)

            rul = lifetime - cycle
            rows.append({
                "unit_id": unit_id,
                "cycle": cycle,
                "temperature": temperature,
                "vibration": vibration,
                "pressure": pressure,
                "rpm": rpm,
                "rul": rul,
            })

    return pd.DataFrame(rows)


def load_raw_data() -> pd.DataFrame:
    """
    Single entry point the rest of the pipeline calls to get raw data.

    Swap this function's body to pull from `sensors.models.SensorReading`
    (pivoted wide per machine/timestamp) once enough real historical data
    has accumulated — nothing else in this file or in train.py needs to
    change, since everything downstream only depends on this function's
    output shape (unit_id, cycle, sensor columns, rul).
    """
    return generate_synthetic_dataset()


# ---------------------------------------------------------------------------
# STEP 2: Labeling
# ---------------------------------------------------------------------------

def add_labels(df: pd.DataFrame, threshold: int = RUL_FAILURE_THRESHOLD) -> pd.DataFrame:
    """Binary target: 1 if this reading falls within `threshold` cycles of
    failure (i.e. maintenance should be scheduled soon), else 0."""
    df = df.copy()
    df[TARGET_COLUMN] = (df["rul"] <= threshold).astype(int)
    return df


# ---------------------------------------------------------------------------
# STEP 3: Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame, window: int = ROLLING_WINDOW) -> pd.DataFrame:
    """
    Adds three families of engineered features per sensor, computed
    *within each unit's own history* (grouped by unit_id) so a rolling
    window never mixes cycles from two different machines:

      1. Rolling mean  (`<sensor>_roll_mean`)  — smooths out sensor noise
         and captures the sensor's recent typical level.
      2. Rolling std    (`<sensor>_roll_std`)   — captures increasing
         *instability*, which often precedes failure even before the mean
         shifts noticeably.
      3. Rate of change (`<sensor>_rate_of_change`) — the cycle-over-cycle
         difference, capturing sudden jumps that a rolling average would
         smooth away.

    A raw sensor reading alone tells you the current value; these engineered
    features tell you the *trend and volatility* behind it, which is what
    actually distinguishes early wear from normal operating noise.

    Rows at the very start of each unit's history don't have enough prior
    cycles to compute a full rolling window/diff, so those rows contain
    NaNs and are dropped by `preprocess()` in the next step.
    """
    df = df.sort_values(["unit_id", "cycle"]).copy()
    grouped = df.groupby("unit_id")

    for sensor in SENSOR_COLUMNS:
        df[f"{sensor}_roll_mean"] = grouped[sensor].transform(lambda s: s.rolling(window).mean())
        df[f"{sensor}_roll_std"] = grouped[sensor].transform(lambda s: s.rolling(window).std())
        df[f"{sensor}_rate_of_change"] = grouped[sensor].transform(lambda s: s.diff())

    return df


# ---------------------------------------------------------------------------
# STEP 4: Cleaning / preprocessing
# ---------------------------------------------------------------------------

def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Final cleanup before modeling:
      - Drops rows with NaN engineered features (the first `window` cycles
        of each unit — there's no way to compute a 5-cycle rolling stat on
        a machine's 2nd cycle, so those rows are removed rather than
        imputed, since imputing a rolling trend would fabricate data).
      - No scaling/normalization is applied here: tree-based models
        (Decision Tree, Random Forest) split on raw feature thresholds and
        are invariant to monotonic feature scaling, so StandardScaler
        would add complexity with zero benefit for these two algorithms.
        (If a distance-based or linear model, e.g. Logistic Regression or
        SVM, is added later, a scaler should be introduced at that point.)
    """
    df = df.dropna(subset=[c for c in FEATURE_COLUMNS if c in df.columns])
    return df


# ---------------------------------------------------------------------------
# STEP 5: Train/test split
# ---------------------------------------------------------------------------

def split_train_test(df: pd.DataFrame, test_size: float = 0.2, random_seed: int = RANDOM_SEED):
    """
    Splits by `unit_id` (grouped split), NOT by random row — this is
    important: rows from the same machine are highly correlated (adjacent
    cycles look very similar), so a plain random row split would leak
    information from a unit's training cycles into its own test cycles,
    making the model look better than it actually is on genuinely unseen
    equipment. GroupShuffleSplit guarantees every unit's rows go entirely
    into either train or test, never split across both.
    """
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    groups = df["unit_id"]

    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_seed)
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))

    return X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx]


def build_dataset():
    """Convenience wrapper running steps 1-4 in order and returning the
    fully engineered, cleaned DataFrame ready for `split_train_test()`."""
    df = load_raw_data()
    df = add_labels(df)
    df = engineer_features(df)
    df = preprocess(df)
    return df
