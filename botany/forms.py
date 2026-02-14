from django.forms import TextInput, Textarea, ModelForm
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

from .models import Plant


class BasePlantForm(ModelForm):
    class Meta:
        model = Plant
        fields = ['name', 'description']
        widgets = {
            "name": TextInput(
                attrs={
                    "class": "text-field w-input",
                    "placeholder": "i.e. 'My Plant'",
                    "aria-label": "Plant Name",
                    "aria-required": "true",
                    "aria-invalid": "false",
                    "autocomplete": "off",
                    "autocorrect": "off",
                    "autocapitalize": "off",
                    "autofocus": "true",
                    "spellcheck": "false",
                }
            ),
            "description": Textarea(
                attrs={
                    "class": "textarea w-input",
                    "rows": 4,
                    "aria-label": "Plant Description",
                    "aria-required": "false",
                    "aria-invalid": "false",
                }
            )
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "")
        name = name.strip()
        name = strip_tags(name)
        if not name:
            raise ValidationError("Name cannot be empty.")
        return name

    def clean_description(self):
        description = self.cleaned_data.get("description", "")
        description = description.strip()
        description = strip_tags(description)
        return description
