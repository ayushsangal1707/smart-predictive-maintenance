from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from equipment.models import Machine

from .audit import log_activity
from .models import AuditLog


class AuditLogTests(TestCase):
    def test_log_activity_captures_object_details(self):
        user = User.objects.create_user("eng", "eng@example.com", "pass12345")
        machine = Machine.objects.create(
            machine_code="BHEL-001", name="Test Machine", machine_type="OTHER", department="OTHER",
            installation_date="2020-01-01", status="ACTIVE",
        )
        log_activity(user, "CREATE", machine, request=None)

        entry = AuditLog.objects.get()
        self.assertEqual(entry.user, user)
        self.assertEqual(entry.action, "CREATE")
        self.assertEqual(entry.model_name, "Machine")
        self.assertEqual(entry.object_id, str(machine.pk))

    def test_log_activity_handles_none_user_and_object(self):
        log_activity(None, "LOGIN", None, request=None)
        entry = AuditLog.objects.get()
        self.assertIsNone(entry.user)
        self.assertEqual(entry.model_name, "")

    def test_login_creates_audit_log_entry(self):
        User.objects.create_user("jdoe", "jdoe@example.com", "pass12345")
        self.client.post(reverse("accounts:login"), {"username": "jdoe", "password": "pass12345"})
        self.assertTrue(AuditLog.objects.filter(action="LOGIN").exists())


class AuditLogViewPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass12345")
        self.engineer = User.objects.create_user("eng", "eng@example.com", "pass12345")
        self.engineer.profile.role = "ENGINEER"
        self.engineer.profile.save()

    def test_admin_can_view_audit_logs(self):
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("core:audit_log_list"))
        self.assertEqual(response.status_code, 200)

    def test_engineer_cannot_view_audit_logs(self):
        self.client.login(username="eng", password="pass12345")
        response = self.client.get(reverse("core:audit_log_list"), follow=True)
        self.assertContains(response, "permission")
