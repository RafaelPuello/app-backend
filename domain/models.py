from django.db import models
from django.utils.translation import gettext_lazy as _

from nfctags.models import AbstractNFCTag


class PlantLabel(AbstractNFCTag):
    title = models.CharField(
        default=_('Plant Label'),
        max_length=255,
        verbose_name=_('title'),
        db_index=True,
        help_text=_('The title of the plant label.')
    )

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['title']
        verbose_name = _('plant label')
        verbose_name_plural = _('plant labels')
