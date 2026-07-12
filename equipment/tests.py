import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import MachineForm
from .models import Machine


class MachineModelTests(TestCase):
    def test_future_installation_date_rejected_by_model_validator(self):
        machine = Machine(
            machine_code="TEST-001", name="Test Machine", machine_type="OTHER", department="OTHER",
            installation_date=timezone.localdate() + datetime.timedelta(days=5), status="ACTIVE",
        )
        with self.assertRaises(ValidationError):
            machine.full_clean()

    def test_status_badge_class_maps_correctly(self):
        machine = Machine(status="ACTIVE")
        self.assertEqual(machine.status_badge_class, "bg-success")
        machine.status = "DECOMMISSIONED"
        self.assertEqual(machine.status_badge_class, "bg-danger")


class MachineFormValidationTests(TestCase):
    def _valid_data(self, **overrides):
        data = {
            "machine_code": "BHEL-TUR-001", "name": "Main Turbine", "machine_type": "TURBINE",
            "department": "TURBINE_PLANT", "location": "Bay 1", "manufacturer": "BHEL",
            "installation_date": "2020-01-01", "status": "ACTIVE", "description": "",
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = MachineForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_machine_code_normalized_to_uppercase(self):
        form = MachineForm(data=self._valid_data(machine_code="bhel-tur-001"))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["machine_code"], "BHEL-TUR-001")

    def test_duplicate_machine_code_rejected(self):
        Machine.objects.create(
            machine_code="BHEL-TUR-001", name="Existing", machine_type="TURBINE", department="TURBINE_PLANT",
            installation_date="2020-01-01", status="ACTIVE",
        )
        form = MachineForm(data=self._valid_data())
        self.assertFalse(form.is_valid())
        self.assertIn("machine_code", form.errors)

    def test_short_name_rejected(self):
        form = MachineForm(data=self._valid_data(name="AB"))
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_future_date_rejected_by_form(self):
        future = (timezone.localdate() + datetime.timedelta(days=10)).isoformat()
        form = MachineForm(data=self._valid_data(installation_date=future))
        self.assertFalse(form.is_valid())
        self.assertIn("installation_date", form.errors)


class MachineViewPermissionTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("mgr", "mgr@example.com", "pass12345")
        self.manager.profile.role = "MANAGER"
        self.manager.profile.save()
        self.engineer = User.objects.create_user("eng", "eng@example.com", "pass12345")
        self.engineer.profile.role = "ENGINEER"
        self.engineer.profile.save()

    def test_manager_cannot_create_machine(self):
        self.client.login(username="mgr", password="pass12345")
        response = self.client.get(reverse("equipment:create"), follow=True)
        self.assertContains(response, "permission")

    def test_engineer_can_create_machine(self):
        self.client.login(username="eng", password="pass12345")
        self.client.post(reverse("equipment:create"), {
            "machine_code": "BHEL-X-001", "name": "New Machine", "machine_type": "OTHER",
            "department": "OTHER", "installation_date": "2021-01-01", "status": "ACTIVE",
        }, follow=True)
        self.assertTrue(Machine.objects.filter(machine_code="BHEL-X-001").exists())

    def test_anonymous_redirected_from_machine_list(self):
        response = self.client.get(reverse("equipment:list"))
        self.assertEqual(response.status_code, 302)
