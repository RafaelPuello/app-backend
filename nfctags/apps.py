from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NfctagsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nfctags'
    label = 'nfctags'
    verbose_name = _("NFC Tags")
