from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import UserPreference, UserProfile


class UserProfileAutoCreationTests(TestCase):
    def test_regular_user_gets_engineer_role_by_default(self):
        user = User.objects.create_user("jdoe", "jdoe@example.com", "pass12345")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.role, "ENGINEER")

    def test_superuser_gets_admin_role_by_default(self):
        user = User.objects.create_superuser("admin", "admin@example.com", "pass12345")
        self.assertEqual(user.profile.role, "ADMIN")

    def test_user_preference_auto_created(self):
        user = User.objects.create_user("jdoe2", "jdoe2@example.com", "pass12345")
        self.assertTrue(UserPreference.objects.filter(user=user).exists())
        self.assertTrue(user.preference.email_notifications_enabled)
        self.assertFalse(user.preference.dark_mode_default)


class RegistrationTests(TestCase):
    def test_registration_creates_user_and_profile_with_role(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "newengineer",
            "email": "newengineer@example.com",
            "first_name": "New",
            "last_name": "Engineer",
            "role": "ENGINEER",
            "employee_id": "EMP123",
            "department": "Turbines",
            "phone": "9999999999",
            "password1": "SuperSecret123!",
            "password2": "SuperSecret123!",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="newengineer")
        self.assertEqual(user.profile.role, "ENGINEER")
        self.assertEqual(user.profile.employee_id, "EMP123")

    def test_duplicate_email_rejected(self):
        User.objects.create_user("existing", "dup@example.com", "pass12345")
        response = self.client.post(reverse("accounts:register"), {
            "username": "another",
            "email": "dup@example.com",
            "role": "ENGINEER",
            "password1": "SuperSecret123!",
            "password2": "SuperSecret123!",
        })
        self.assertContains(response, "already exists")
        self.assertFalse(User.objects.filter(username="another").exists())


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("jdoe", "jdoe@example.com", "pass12345")

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "jdoe", "password": "pass12345",
        })
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_login_wrong_password_fails(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "jdoe", "password": "wrongpassword",
        })
        self.assertEqual(response.status_code, 200)  # re-renders form, no redirect
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_requires_post(self):
        self.client.login(username="jdoe", password="pass12345")
        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 405)  # GET not allowed on LogoutView

    def test_profile_page_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)


class RoleRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("mgr", "mgr@example.com", "pass12345")
        self.manager.profile.role = "MANAGER"
        self.manager.profile.save()

    def test_non_admin_blocked_from_audit_logs(self):
        self.client.login(username="mgr", password="pass12345")
        response = self.client.get(reverse("core:audit_log_list"), follow=True)
        self.assertContains(response, "permission")
