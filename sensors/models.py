from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from equipment.models import Machine

SOURCE_MANUAL = "MANUAL"
SOURCE_CSV = "CSV"
SOURCE_EXCEL = "EXCEL"

SOURCE_CHOICES = [
    (SOURCE_MANUAL, "Manual Entry"),
    (SOURCE_CSV, "CSV Upload"),
    (SOURCE_EXCEL, "Excel Upload"),
]

COMMON_UNITS = [
    ("C", "°C"),
    ("F", "°F"),
    ("MM_S", "mm/s (vibration)"),
    ("BAR", "bar (pressure)"),
    ("PSI", "psi (pressure)"),
    ("RPM", "RPM"),
    ("A", "A (current)"),
    ("V", "V (voltage)"),
    ("PERCENT", "%"),
    ("HZ", "Hz"),
    ("OTHER", "Other"),
]


class SensorDefinition(models.Model):
    """
    Describes a single sensor attached to a Machine (e.g. "Bearing
    Temperature" on Turbine A). Stored separately from the readings
    themselves (long/EAV-lite format, per the Prompt 1 architecture) so a
    new sensor type never requires a schema migration — just a new row
    here.
    """

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="sensor_definitions")
    sensor_name = models.CharField(max_length=100, help_text="e.g. Bearing Temperature, Vibration, RPM")
    unit = models.CharField(max_length=20, choices=COMMON_UNITS, default="OTHER")
    normal_min = models.FloatField(help_text="Lower bound of the normal operating range")
    normal_max = models.FloatField(help_text="Upper bound of the normal operating range")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["machine", "sensor_name"]
        unique_together = [("machine", "sensor_name")]

    def __str__(self):
        return f"{self.machine.machine_code} — {self.sensor_name} ({self.get_unit_display()})"

    def clean(self):
        if self.normal_min is not None and self.normal_max is not None:
            if self.normal_min >= self.normal_max:
                raise ValidationError("Normal minimum must be less than normal maximum.")


class SensorReadingQuerySet(models.QuerySet):
    def out_of_range(self):
        return self.filter(
            Q(value__lt=F("sensor__normal_min")) | Q(value__gt=F("sensor__normal_max"))
        )

    def in_range(self):
        return self.filter(
            value__gte=F("sensor__normal_min"), value__lte=F("sensor__normal_max")
        )


class SensorReading(models.Model):
    """A single timestamped measurement from one SensorDefinition."""

    sensor = models.ForeignKey(SensorDefinition, on_delete=models.CASCADE, related_name="readings")
    value = models.FloatField()
    recorded_at = models.DateTimeField(help_text="When the reading was taken")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sensor_readings"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SensorReadingQuerySet.as_manager()

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["sensor", "recorded_at"]),
            models.Index(fields=["recorded_at"]),
        ]

    def __str__(self):
        return f"{self.sensor.sensor_name} = {self.value} @ {self.recorded_at:%Y-%m-%d %H:%M}"

    def clean(self):
        if self.recorded_at and self.recorded_at > timezone.now():
            raise ValidationError("Recorded date/time cannot be in the future.")

    @property
    def is_out_of_range(self):
        return self.value < self.sensor.normal_min or self.value > self.sensor.normal_max
