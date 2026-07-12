from django import forms
from django.contrib.auth.models import User

from .models import Comment, MaintenanceRequest, STATUS_CHOICES


def _bootstrapify(fields, select_names=()):
    for name, field in fields.items():
        existing = field.widget.attrs.get("class", "")
        css_class = "form-select" if name in select_names else "form-control"
        field.widget.attrs["class"] = (existing + " " + css_class).strip()


class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = ["machine", "title", "description", "priority"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self.fields, select_names=("machine", "priority"))

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters long.")
        return title


class AssignEngineerForm(forms.Form):
    engineer = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__role="ENGINEER").order_by("username"),
        label="Assign Engineer",
        empty_label="Select an engineer...",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["engineer"].widget.attrs["class"] = "form-select"


class ScheduleForm(forms.Form):
    scheduled_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
        label="Scheduled Date/Time",
    )


class StatusUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=STATUS_CHOICES)
    note = forms.CharField(max_length=255, required=False, widget=forms.TextInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].widget.attrs["class"] = "form-select"
        self.fields["note"].widget.attrs["class"] = "form-control"
        self.fields["note"].widget.attrs["placeholder"] = "Optional note about this status change"


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Add a comment..."})}

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("Comment cannot be empty.")
        return body
