import os

from django import forms
from django.utils import timezone

from equipment.models import Machine

from .models import SensorDefinition, SensorReading

MAX_UPLOAD_SIZE_MB = 5
ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _bootstrapify(fields, select_names=()):
    for name, field in fields.items():
        existing = field.widget.attrs.get("class", "")
        css_class = "form-select" if name in select_names else "form-control"
        field.widget.attrs["class"] = (existing + " " + css_class).strip()


class SensorDefinitionForm(forms.ModelForm):
    class Meta:
        model = SensorDefinition
        fields = ["machine", "sensor_name", "unit", "normal_min", "normal_max", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self.fields, select_names=("machine", "unit"))
        self.fields["is_active"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned = super().clean()
        normal_min = cleaned.get("normal_min")
        normal_max = cleaned.get("normal_max")
        if normal_min is not None and normal_max is not None and normal_min >= normal_max:
            raise forms.ValidationError("Normal minimum must be less than normal maximum.")
        return cleaned


class ManualReadingForm(forms.ModelForm):
    """
    Includes a non-model `machine` field purely so the template's JS can
    filter the `sensor` dropdown to that machine's sensors via an AJAX call
    (see /sensors/api/machines/<id>/sensors/ and static/js/sensor_entry.js).
    The actual FK saved on SensorReading is `sensor` only.
    """

    machine = forms.ModelChoiceField(queryset=Machine.objects.all(), required=True, label="Machine")

    class Meta:
        model = SensorReading
        fields = ["machine", "sensor", "value", "recorded_at"]
        widgets = {
            "recorded_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sensor"].queryset = SensorDefinition.objects.filter(is_active=True).select_related("machine")
        self.fields["sensor"].label_from_instance = lambda obj: f"{obj.sensor_name} ({obj.get_unit_display()})"
        if not self.initial.get("recorded_at") and not self.data:
            self.fields["recorded_at"].initial = timezone.now().strftime("%Y-%m-%dT%H:%M")
        _bootstrapify(self.fields, select_names=("machine", "sensor"))

    def clean(self):
        cleaned = super().clean()
        machine = cleaned.get("machine")
        sensor = cleaned.get("sensor")
        if machine and sensor and sensor.machine_id != machine.id:
            raise forms.ValidationError("Selected sensor does not belong to the selected machine.")
        return cleaned

    def clean_recorded_at(self):
        recorded_at = self.cleaned_data["recorded_at"]
        if recorded_at > timezone.now():
            raise forms.ValidationError("Recorded date/time cannot be in the future.")
        return recorded_at


class ReadingUploadForm(forms.Form):
    """
    Used for both CSV and Excel uploads — the view/parser decides which
    parser to use based on the file extension, so this one form covers both
    upload types.

    Expected file columns: sensor_name, value, recorded_at (recorded_at is
    optional per-row; blank rows default to "now").
    """

    machine = forms.ModelChoiceField(queryset=Machine.objects.all(), label="Machine")
    file = forms.FileField(label="CSV or Excel file")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self.fields, select_names=("machine",))

    def clean_file(self):
        f = self.cleaned_data["file"]

        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise forms.ValidationError(
                f"Unsupported file type '{ext}'. Please upload a .csv, .xlsx, or .xls file."
            )

        max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if f.size > max_bytes:
            raise forms.ValidationError(f"File is too large. Maximum allowed size is {MAX_UPLOAD_SIZE_MB} MB.")

        if f.size == 0:
            raise forms.ValidationError("The uploaded file is empty.")

        return f
