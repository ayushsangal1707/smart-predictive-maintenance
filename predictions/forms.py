from django import forms

from equipment.models import Machine


class RunPredictionForm(forms.Form):
    """Simple machine picker for the 'New Prediction' page."""

    machine = forms.ModelChoiceField(
        queryset=Machine.objects.all().order_by("name"),
        label="Machine",
        empty_label="Select a machine...",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["machine"].widget.attrs["class"] = "form-select"
