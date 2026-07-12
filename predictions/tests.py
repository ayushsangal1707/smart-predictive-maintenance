import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from equipment.models import Machine
from sensors.models import SensorDefinition, SensorReading

from .ml.predict import PredictionError, predict_for_machine
from .models import ModelVersion, risk_level_for_probability


class RiskLevelThresholdTests(TestCase):
    def test_thresholds(self):
        self.assertEqual(risk_level_for_probability(0.0), "LOW")
        self.assertEqual(risk_level_for_probability(0.24), "LOW")
        self.assertEqual(risk_level_for_probability(0.25), "MEDIUM")
        self.assertEqual(risk_level_for_probability(0.49), "MEDIUM")
        self.assertEqual(risk_level_for_probability(0.5), "HIGH")
        self.assertEqual(risk_level_for_probability(0.74), "HIGH")
        self.assertEqual(risk_level_for_probability(0.75), "CRITICAL")
        self.assertEqual(risk_level_for_probability(1.0), "CRITICAL")


class ModelVersionOnlyOneActiveTests(TestCase):
    def test_activating_a_new_version_deactivates_others(self):
        v1 = ModelVersion.objects.create(
            version_name="v1", algorithm="DecisionTreeClassifier", trained_at=timezone.now(),
            file_path="model_v1.pkl", is_active=True,
        )
        v2 = ModelVersion.objects.create(
            version_name="v2", algorithm="RandomForestClassifier", trained_at=timezone.now(),
            file_path="model_v1.pkl", is_active=True,
        )
        v1.refresh_from_db()
        self.assertFalse(v1.is_active)
        self.assertTrue(v2.is_active)
        self.assertEqual(ModelVersion.objects.filter(is_active=True).count(), 1)


class PredictionEngineTests(TestCase):
    """
    Uses the real model_v1.pkl bundled in predictions/ml/model_registry/
    (trained in Prompt 5) rather than a mock, so these tests exercise the
    actual prediction pipeline end-to-end, same as it will run in
    production.
    """

    def setUp(self):
        self.user = User.objects.create_user("eng", "eng@example.com", "pass12345")
        ModelVersion.objects.create(
            version_name="v1", algorithm="DecisionTreeClassifier", trained_at=timezone.now(),
            file_path="model_v1.pkl", feature_columns=[], metrics={}, is_active=True,
        )
        self.machine = Machine.objects.create(
            machine_code="BHEL-PRED-001", name="Prediction Test Machine", machine_type="TURBINE",
            department="TURBINE_PLANT", installation_date="2020-01-01", status="ACTIVE",
        )

    def _add_sensors_and_readings(self, values):
        base_time = timezone.now() - datetime.timedelta(hours=10)
        defs = {}
        for name, unit, lo, hi, key in [
            ("Bearing Temperature", "C", 20, 80, "temperature"),
            ("Motor Vibration", "MM_S", 0, 5, "vibration"),
            ("Oil Pressure", "BAR", 3, 8, "pressure"),
            ("Shaft RPM", "RPM", 1000, 2000, "rpm"),
        ]:
            defs[key] = SensorDefinition.objects.create(
                machine=self.machine, sensor_name=name, unit=unit, normal_min=lo, normal_max=hi,
            )
        for key, vals in values.items():
            for i, v in enumerate(vals):
                SensorReading.objects.create(
                    sensor=defs[key], value=v, recorded_at=base_time + datetime.timedelta(hours=i),
                    source="MANUAL", created_by=self.user,
                )

    def test_no_active_model_raises_clear_error(self):
        ModelVersion.objects.all().delete()
        with self.assertRaisesMessage(PredictionError, "No active prediction model"):
            predict_for_machine(self.machine, user=self.user)

    def test_missing_sensors_raises_clear_error(self):
        with self.assertRaisesMessage(PredictionError, "missing a required sensor"):
            predict_for_machine(self.machine, user=self.user)

    def test_insufficient_reading_history_raises_clear_error(self):
        self._add_sensors_and_readings({
            "temperature": [45, 46], "vibration": [1.2, 1.3], "pressure": [5.0, 5.1], "rpm": [1500, 1495],
        })
        with self.assertRaisesMessage(PredictionError, "Not enough history"):
            predict_for_machine(self.machine, user=self.user)

    def test_healthy_machine_predicts_low_risk(self):
        self._add_sensors_and_readings({
            "temperature": [45, 46, 47, 46, 48, 49],
            "vibration": [1.2, 1.3, 1.2, 1.4, 1.3, 1.2],
            "pressure": [5.0, 5.1, 5.0, 4.9, 5.0, 5.1],
            "rpm": [1500, 1495, 1500, 1505, 1498, 1500],
        })
        prediction = predict_for_machine(self.machine, user=self.user)
        self.assertEqual(prediction.risk_level, "LOW")
        self.assertEqual(prediction.machine, self.machine)
        self.assertIsNotNone(prediction.input_snapshot)

    def test_degraded_machine_predicts_high_risk(self):
        self._add_sensors_and_readings({
            "temperature": [70, 75, 78, 82, 85, 88],
            "vibration": [3.5, 3.8, 4.2, 4.5, 4.8, 5.2],
            "pressure": [3.5, 3.3, 3.1, 2.9, 2.7, 2.5],
            "rpm": [1200, 1150, 1100, 1050, 1000, 950],
        })
        prediction = predict_for_machine(self.machine, user=self.user)
        self.assertIn(prediction.risk_level, ("HIGH", "CRITICAL"))
        self.assertGreater(prediction.failure_probability, 0.5)
