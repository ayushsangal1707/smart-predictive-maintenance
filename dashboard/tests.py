"""
dashboard/tests.py
---------------------
Integration tests: exercise the full cross-app workflow end-to-end, the
same way a real user would move through the system — register, log in,
add a machine, define sensors, upload readings, run a prediction, see it
reflected on the dashboard, raise a maintenance request from it, assign
an engineer, complete the work, and export a report. Placed here (rather
than split per-app) since the dashboard is the one app that touches every
other module, making it the natural home for a whole-system test.
"""

import datetime

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from equipment.models import Machine
from maintenance.models import MaintenanceRequest
from predictions.models import ModelVersion, Prediction
from sensors.models import SensorDefinition, SensorReading


class FullWorkflowIntegrationTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass12345")
        self.engineer = User.objects.create_user("eng1", "eng1@example.com", "pass12345")
        self.engineer.profile.role = "ENGINEER"
        self.engineer.profile.save()

        ModelVersion.objects.create(
            version_name="v1", algorithm="DecisionTreeClassifier", trained_at=timezone.now(),
            file_path="model_v1.pkl", feature_columns=[], metrics={}, is_active=True,
        )

    def test_full_plant_maintenance_workflow(self):
        client = self.client

        # 1. Login lands on the dashboard
        response = client.post(reverse("accounts:login"), {"username": "admin", "password": "pass12345"})
        self.assertRedirects(response, reverse("dashboard:home"))

        # 2. Create a machine
        response = client.post(reverse("equipment:create"), {
            "machine_code": "BHEL-INT-001", "name": "Integration Test Turbine", "machine_type": "TURBINE",
            "department": "TURBINE_PLANT", "installation_date": "2019-01-01", "status": "ACTIVE",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        machine = Machine.objects.get(machine_code="BHEL-INT-001")

        # 3. Define sensors
        for name, unit, lo, hi in [
            ("Bearing Temperature", "C", 20, 80), ("Motor Vibration", "MM_S", 0, 5),
            ("Oil Pressure", "BAR", 3, 8), ("Shaft RPM", "RPM", 1000, 2000),
        ]:
            client.post(reverse("sensors:definition_create"), {
                "machine": machine.id, "sensor_name": name, "unit": unit,
                "normal_min": lo, "normal_max": hi, "is_active": "on",
            })
        self.assertEqual(SensorDefinition.objects.filter(machine=machine).count(), 4)

        # 4. Upload degraded sensor readings via CSV (simulating a machine heading toward failure)
        csv_rows = ["sensor_name,value,recorded_at"]
        base = timezone.now() - datetime.timedelta(hours=6)
        degraded = {
            "Bearing Temperature": [70, 75, 78, 82, 85, 88],
            "Motor Vibration": [3.5, 3.8, 4.2, 4.5, 4.8, 5.2],
            "Oil Pressure": [3.5, 3.3, 3.1, 2.9, 2.7, 2.5],
            "Shaft RPM": [1200, 1150, 1100, 1050, 1000, 950],
        }
        for sensor_name, values in degraded.items():
            for i, v in enumerate(values):
                ts = (base + datetime.timedelta(hours=i)).strftime("%Y-%m-%d %H:%M")
                csv_rows.append(f"{sensor_name},{v},{ts}")
        csv_content = "\n".join(csv_rows) + "\n"
        upload = SimpleUploadedFile("readings.csv", csv_content.encode(), content_type="text/csv")
        response = client.post(reverse("sensors:upload"), {"machine": machine.id, "file": upload}, follow=True)
        self.assertContains(response, "imported")
        self.assertEqual(SensorReading.objects.filter(sensor__machine=machine).count(), 24)

        # 5. Run a prediction — should come back High/Critical given the degraded data
        response = client.post(reverse("predictions:run"), {"machine": machine.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        prediction = Prediction.objects.filter(machine=machine).first()
        self.assertIsNotNone(prediction)
        self.assertIn(prediction.risk_level, ("HIGH", "CRITICAL"))

        # 6. Dashboard reflects the new machine and its risk
        response = client.get(reverse("dashboard:home"))
        self.assertContains(response, "Integration Test Turbine")

        # 7. Create a maintenance request directly from the prediction
        response = client.post(f"{reverse('maintenance:create')}?prediction={prediction.pk}", {
            "machine": machine.id,
            "title": f"Investigate {prediction.get_risk_level_display()} risk on {machine.name}",
            "priority": "CRITICAL",
            "description": "Auto-suggested from prediction alert.",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        maintenance_request = MaintenanceRequest.objects.get(machine=machine)
        self.assertEqual(maintenance_request.source_prediction, prediction)

        # 8. Assign an engineer
        client.post(
            reverse("maintenance:assign", args=[maintenance_request.pk]),
            {"engineer": self.engineer.pk}, follow=True,
        )
        maintenance_request.refresh_from_db()
        self.assertEqual(maintenance_request.assigned_engineer, self.engineer)
        self.assertEqual(maintenance_request.status, "ASSIGNED")

        # 9. Engineer logs in, does the work, marks it complete
        client.logout()
        client.login(username="eng1", password="pass12345")
        client.post(
            reverse("maintenance:update_status", args=[maintenance_request.pk]),
            {"status": "IN_PROGRESS", "note": "Started inspection"},
        )
        client.post(
            reverse("maintenance:add_comment", args=[maintenance_request.pk]),
            {"body": "Replaced worn bearing, vibration back to normal."},
        )
        client.post(
            reverse("maintenance:update_status", args=[maintenance_request.pk]),
            {"status": "COMPLETED", "note": "Repair complete"},
        )
        maintenance_request.refresh_from_db()
        self.assertEqual(maintenance_request.status, "COMPLETED")
        self.assertIsNotNone(maintenance_request.completed_at)
        self.assertEqual(maintenance_request.comments.count(), 1)
        self.assertEqual(maintenance_request.status_history.count(), 3)  # ASSIGNED(auto) + IN_PROGRESS + COMPLETED

        # 10. Dashboard still renders fine after all this activity
        response = client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)

        # 11. Admin exports reports of everything that just happened
        client.logout()
        client.login(username="admin", password="pass12345")
        self.assertEqual(client.get(reverse("reports:export_machines", args=["csv"])).status_code, 200)
        self.assertEqual(client.get(reverse("reports:export_maintenance", args=["excel"])).status_code, 200)
        self.assertEqual(client.get(reverse("reports:export_summary_pdf")).status_code, 200)

        # 12. Audit trail captured the key actions along the way
        from core.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(action="CREATE", model_name="Machine").exists())
        self.assertTrue(AuditLog.objects.filter(action="PREDICT").exists())
        self.assertTrue(AuditLog.objects.filter(action="CREATE", model_name="MaintenanceRequest").exists())
        self.assertTrue(AuditLog.objects.filter(action="EXPORT").exists())
