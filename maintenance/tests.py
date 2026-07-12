from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from equipment.models import Machine

from .models import MaintenanceRequest, Notification
from .services import add_comment, assign_engineer, change_status


class MaintenanceServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("mgr", "mgr@example.com", "pass12345")
        self.manager.profile.role = "MANAGER"
        self.manager.profile.save()
        self.engineer = User.objects.create_user("eng", "eng@example.com", "pass12345")
        self.engineer.profile.role = "ENGINEER"
        self.engineer.profile.save()
        self.machine = Machine.objects.create(
            machine_code="BHEL-001", name="Test Machine", machine_type="OTHER", department="OTHER",
            installation_date="2020-01-01", status="ACTIVE",
        )
        self.request_obj = MaintenanceRequest.objects.create(
            machine=self.machine, title="Fix bearing noise", priority="HIGH", requested_by=self.manager,
        )

    def test_assign_engineer_auto_advances_open_status(self):
        self.assertEqual(self.request_obj.status, "OPEN")
        assign_engineer(self.request_obj, self.engineer, assigned_by=self.manager)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, "ASSIGNED")
        self.assertEqual(self.request_obj.assigned_engineer, self.engineer)

    def test_assign_engineer_notifies_engineer(self):
        assign_engineer(self.request_obj, self.engineer, assigned_by=self.manager)
        self.assertTrue(Notification.objects.filter(user=self.engineer).exists())

    def test_change_status_creates_history_entry(self):
        change_status(self.request_obj, "IN_PROGRESS", changed_by=self.manager, note="Started work")
        self.assertEqual(self.request_obj.status_history.count(), 1)
        history = self.request_obj.status_history.first()
        self.assertEqual(history.new_status, "IN_PROGRESS")
        self.assertEqual(history.note, "Started work")

    def test_change_status_to_completed_sets_completed_at(self):
        self.assertIsNone(self.request_obj.completed_at)
        change_status(self.request_obj, "COMPLETED", changed_by=self.manager)
        self.request_obj.refresh_from_db()
        self.assertIsNotNone(self.request_obj.completed_at)

    def test_actor_is_not_notified_about_their_own_change(self):
        change_status(self.request_obj, "IN_PROGRESS", changed_by=self.manager)
        # requested_by IS the manager here, so no notification should be
        # created for them about their own action.
        self.assertFalse(Notification.objects.filter(user=self.manager).exists())

    def test_add_comment_notifies_other_party(self):
        assign_engineer(self.request_obj, self.engineer, assigned_by=self.manager)
        Notification.objects.all().delete()
        add_comment(self.request_obj, author=self.engineer, body="Found the issue.")
        self.assertTrue(Notification.objects.filter(user=self.manager).exists())
        self.assertFalse(Notification.objects.filter(user=self.engineer).exists())


class MaintenancePermissionTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("mgr", "mgr@example.com", "pass12345")
        self.manager.profile.role = "MANAGER"
        self.manager.profile.save()
        self.engineer1 = User.objects.create_user("eng1", "eng1@example.com", "pass12345")
        self.engineer1.profile.role = "ENGINEER"
        self.engineer1.profile.save()
        self.engineer2 = User.objects.create_user("eng2", "eng2@example.com", "pass12345")
        self.engineer2.profile.role = "ENGINEER"
        self.engineer2.profile.save()
        self.machine = Machine.objects.create(
            machine_code="BHEL-002", name="Test Machine 2", machine_type="OTHER", department="OTHER",
            installation_date="2020-01-01", status="ACTIVE",
        )
        self.request_obj = MaintenanceRequest.objects.create(
            machine=self.machine, title="Investigate vibration", priority="MEDIUM", requested_by=self.manager,
            assigned_engineer=self.engineer1,
        )

    def test_unassigned_engineer_cannot_assign(self):
        self.client.login(username="eng2", password="pass12345")
        response = self.client.post(
            reverse("maintenance:assign", args=[self.request_obj.pk]),
            {"engineer": self.engineer2.pk}, follow=True,
        )
        self.assertContains(response, "Only an Admin or Manager")
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.assigned_engineer, self.engineer1)

    def test_assigned_engineer_can_update_status(self):
        self.client.login(username="eng1", password="pass12345")
        self.client.post(
            reverse("maintenance:update_status", args=[self.request_obj.pk]),
            {"status": "IN_PROGRESS", "note": ""}, follow=True,
        )
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, "IN_PROGRESS")

    def test_short_title_rejected_on_create(self):
        self.client.login(username="mgr", password="pass12345")
        response = self.client.post(reverse("maintenance:create"), {
            "machine": self.machine.pk, "title": "Hi", "priority": "LOW", "description": "",
        })
        self.assertContains(response, "at least 5 characters")
