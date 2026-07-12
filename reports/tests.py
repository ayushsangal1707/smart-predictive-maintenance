from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from equipment.models import Machine

from .generators import generate_summary_pdf, machines_dataframe


class ReportGeneratorTests(TestCase):
    def setUp(self):
        Machine.objects.create(
            machine_code="BHEL-001", name="Test Machine", machine_type="TURBINE", department="TURBINE_PLANT",
            installation_date="2020-01-01", status="ACTIVE",
        )

    def test_machines_dataframe_has_expected_columns(self):
        df = machines_dataframe(Machine.objects.all())
        self.assertEqual(len(df), 1)
        self.assertIn("Machine Code", df.columns)
        self.assertIn("Status", df.columns)

    def test_summary_pdf_is_a_valid_pdf(self):
        stats = {
            "total_machines": 1, "active_machines": 1, "under_maintenance_machines": 0,
            "risk_counts": {"Low": 1, "Medium": 0, "High": 0, "Critical": 0},
            "open_requests": [],
        }
        response = generate_summary_pdf(stats)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))


class ReportExportViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("eng", "eng@example.com", "pass12345")
        Machine.objects.create(
            machine_code="BHEL-001", name="Test Machine", machine_type="TURBINE", department="TURBINE_PLANT",
            installation_date="2020-01-01", status="ACTIVE",
        )
        self.client.login(username="eng", password="pass12345")

    def test_csv_export_returns_csv(self):
        response = self.client.get(reverse("reports:export_machines", args=["csv"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_excel_export_returns_xlsx(self):
        response = self.client.get(reverse("reports:export_machines", args=["excel"]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])

    def test_invalid_format_returns_400(self):
        response = self.client.get(reverse("reports:export_machines", args=["xml"]))
        self.assertEqual(response.status_code, 400)

    def test_pdf_summary_export(self):
        response = self.client.get(reverse("reports:export_summary_pdf"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_export_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("reports:export_machines", args=["csv"]))
        self.assertEqual(response.status_code, 302)
