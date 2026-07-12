from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from equipment.models import Machine

from .models import SensorDefinition, SensorReading
from .utils import UploadParseError, process_reading_upload


class SensorDefinitionValidationTests(TestCase):
    def setUp(self):
        self.machine = Machine.objects.create(
            machine_code="BHEL-001", name="Test Machine", machine_type="OTHER", department="OTHER",
            installation_date="2020-01-01", status="ACTIVE",
        )

    def test_min_must_be_less_than_max(self):
        definition = SensorDefinition(
            machine=self.machine, sensor_name="Bad Sensor", unit="C", normal_min=100, normal_max=50,
        )
        with self.assertRaises(ValidationError):
            definition.full_clean()


class SensorReadingOutOfRangeTests(TestCase):
    def setUp(self):
        self.machine = Machine.objects.create(
            machine_code="BHEL-002", name="Test Machine 2", machine_type="OTHER", department="OTHER",
            installation_date="2020-01-01", status="ACTIVE",
        )
        self.sensor = SensorDefinition.objects.create(
            machine=self.machine, sensor_name="Temp", unit="C", normal_min=20, normal_max=80,
        )

    def test_is_out_of_range_property(self):
        normal = SensorReading.objects.create(sensor=self.sensor, value=50, recorded_at=timezone.now())
        high = SensorReading.objects.create(sensor=self.sensor, value=95, recorded_at=timezone.now())
        self.assertFalse(normal.is_out_of_range)
        self.assertTrue(high.is_out_of_range)

    def test_out_of_range_queryset_filter(self):
        SensorReading.objects.create(sensor=self.sensor, value=50, recorded_at=timezone.now())
        SensorReading.objects.create(sensor=self.sensor, value=95, recorded_at=timezone.now())
        self.assertEqual(SensorReading.objects.out_of_range().count(), 1)
        self.assertEqual(SensorReading.objects.in_range().count(), 1)


class CSVUploadParsingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("eng", "eng@example.com", "pass12345")
        self.machine = Machine.objects.create(
            machine_code="BHEL-003", name="Upload Test Machine", machine_type="OTHER", department="OTHER",
            installation_date="2020-01-01", status="ACTIVE",
        )
        self.sensor = SensorDefinition.objects.create(
            machine=self.machine, sensor_name="Temperature", unit="C", normal_min=20, normal_max=80,
        )

    def test_valid_rows_imported_and_invalid_rows_reported(self):
        csv_content = (
            "sensor_name,value,recorded_at\n"
            "Temperature,55.2,2026-06-01 08:00\n"
            "Temperature,not_a_number,2026-06-01 09:00\n"
            "Unknown Sensor,10,2026-06-01 09:00\n"
        )
        upload = SimpleUploadedFile("readings.csv", csv_content.encode(), content_type="text/csv")
        result = process_reading_upload(upload, self.machine, self.user)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped"], 2)
        self.assertEqual(SensorReading.objects.count(), 1)

    def test_missing_required_column_raises_parse_error(self):
        upload = SimpleUploadedFile("bad.csv", b"foo,bar\n1,2\n", content_type="text/csv")
        with self.assertRaises(UploadParseError):
            process_reading_upload(upload, self.machine, self.user)

    def test_upload_to_machine_with_no_sensors_raises_parse_error(self):
        other_machine = Machine.objects.create(
            machine_code="BHEL-004", name="No Sensors Machine", machine_type="OTHER", department="OTHER",
            installation_date="2020-01-01", status="ACTIVE",
        )
        upload = SimpleUploadedFile("r.csv", b"sensor_name,value\nX,1\n", content_type="text/csv")
        with self.assertRaises(UploadParseError):
            process_reading_upload(upload, other_machine, self.user)

    def test_empty_file_raises_parse_error(self):
        upload = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")
        with self.assertRaises(UploadParseError):
            process_reading_upload(upload, self.machine, self.user)
