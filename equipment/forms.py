import re

from django import forms
from django.utils import timezone

from .models import Machine


class MachineForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = [
            "machine_code",
            "name",
            "machine_type",
            "department",
            "location",
            "manufacturer",
            "installation_date",
            "status",
            "description",
        ]
        widgets = {
            "installation_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            existing = field.widget.attrs.get("class", "")
            css_class = "form-select" if name in ("machine_type", "department", "status") else "form-control"
            field.widget.attrs["class"] = (existing + " " + css_class).strip()
        self.fields["machine_code"].widget.attrs["placeholder"] = "e.g. BHEL-TUR-001"

    def clean_machine_code(self):
        code = self.cleaned_data["machine_code"].strip().upper()
        if not re.match(r"^[A-Z0-9\-]+$", code):
            raise forms.ValidationError(
                "Machine code can only contain letters, numbers, and hyphens."
            )
        # Uniqueness excluding the current instance (so editing a machine
        # without changing its own code doesn't falsely fail this check).
        qs = Machine.objects.filter(machine_code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A machine with this code already exists.")
        return code

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 3:
            raise forms.ValidationError("Machine name must be at least 3 characters long.")
        return name

    def clean_installation_date(self):
        date = self.cleaned_data["installation_date"]
        if date > timezone.localdate():
            raise forms.ValidationError("Installation date cannot be in the future.")
        return date
