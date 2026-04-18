from django.db import models
from django.utils.translation import gettext_lazy as _

from nfctags.models import AbstractNFCTag


class PlantLabel(AbstractNFCTag):
    """NFC label physically attached to a plant in the user's collection."""

    title = models.CharField(
        default=_("Plant Label"),
        max_length=255,
        verbose_name=_("title"),
        db_index=True,
        help_text=_("The title of the plant label."),
    )
    plant = models.ForeignKey(
        "botany.Plant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nfc_labels",
        verbose_name=_("plant"),
        help_text=_("The plant this NFC label is bound to."),
    )

    def __str__(self) -> str:
        if self.plant_id is not None:
            return f"Label {self.uuid} \u2192 {self.plant.name}"  # noqa: RUF001
        return self.title

    class Meta:
        ordering = ["title"]
        verbose_name = _("plant label")
        verbose_name_plural = _("plant labels")
