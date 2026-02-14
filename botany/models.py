import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from modelcluster.models import ClusterableModel
from modelcluster.fields import ParentalKey


class Plant(ClusterableModel):
    """
    Model representing a plant in the botany app.
    """
    name = models.CharField(
        max_length=255,
        verbose_name=_('name'),
        db_index=True,
        help_text=_('The name of the plant.')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('description'),
        help_text=_('A brief description of the plant.')
    )
    gbif_id = models.PositiveBigIntegerField(
        blank=True,
        default=6,
        verbose_name=_('GBIF ID'),
        help_text=_('The GBIF ID of the plant.')
    )
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='plants',
        verbose_name=_('user'),
        help_text=_('The user who owns this plant.')
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        unique=True,
    )
    created_at = models.DateTimeField(
        db_index=True,
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name


class PlantGalleryImage(models.Model):
    plant = ParentalKey(
        Plant,
        on_delete=models.CASCADE,
        related_name='gallery_images'
    )
    image = models.ImageField(
        upload_to='plants/gallery/',
        verbose_name=_('image'),
        help_text=_('Upload an image for this plant.')
    )
    caption = models.CharField(
        blank=True,
        max_length=250
    )
    sort_order = models.IntegerField(
        null=True,
        blank=True,
        editable=False
    )

    sort_order_field = "sort_order"

    class Meta:
        ordering = ["sort_order"]


class PlantJournalEntry(models.Model):
    plant = ParentalKey(
        Plant,
        related_name='journal_entries',
        on_delete=models.CASCADE
    )
    body = models.TextField()
    watered = models.BooleanField(
        default=False,
        verbose_name=_('Watered'),
        help_text=_('Indicates if the plant was watered.')
    )
    fertilized = models.BooleanField(
        default=False,
        verbose_name=_('Fertilized'),
        help_text=_('Indicates if the plant was fertilized.')
    )
    repotted = models.BooleanField(
        default=False,
        verbose_name=_('Repotted'),
        help_text=_('Indicates if the plant was repotted.')
    )
    rotated = models.BooleanField(
        default=False,
        verbose_name=_('Rotated'),
        help_text=_('Indicates if the plant was rotated.')
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        unique=True,
    )
    created_at = models.DateTimeField(
        db_index=True,
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Journal Entry for {self.plant}"
