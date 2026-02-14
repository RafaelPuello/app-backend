from django import forms
from django.conf import settings

from . import get_nfctag_model

NFCTag = get_nfctag_model()


class BaseNFCTagForm(forms.ModelForm):
    class Meta:
        model = NFCTag
        exclude = ["uuid", "uid", "user", "active", "created_at", "updated_at"]


def get_nfctag_base_form():
    base_form_override = getattr(settings, "NFC_TAG_FORM_BASE", "")
    if base_form_override:
        from django.utils.module_loading import import_string

        base_form = import_string(base_form_override)
    else:
        base_form = BaseNFCTagForm
    return base_form
