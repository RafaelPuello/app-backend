import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey

from .validators import validate_ascii_mirror_uid


class AbstractNFCTag(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        unique=True,
    )
    uid = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        validators=[validate_ascii_mirror_uid]
    )
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    active = models.BooleanField(
        default=True
    )
    created_at = models.DateTimeField(
        db_index=True,
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"NFC Tag: {self.uid}"

    def __gt__(self, other):
        return self.uid > other.uid

    def __lt__(self, other):
        return self.uid < other.uid

    class Meta:
        abstract = True
        ordering = ['uid']
        verbose_name = _("NFC Tag")
        verbose_name_plural = _("NFC Tags")

    @property
    def is_available_to_register(self) -> bool:
        """
        Returns whether the NFC tag is available to be registered.
        """
        return self.active and self.user is None


class GenericAbstractNFCTag(AbstractNFCTag):
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        editable=False,
        null=True,
        blank=True,
    )
    content_object = GenericForeignKey()

    class Meta:
        abstract = True


class AbstractIntegerNFCTag(GenericAbstractNFCTag):
    object_id = models.IntegerField(
        db_index=True,
        null=True,
        blank=True,
        editable=False
    )

    class Meta:
        abstract = True


class AbstractUUIDNFCTag(GenericAbstractNFCTag):
    object_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        editable=False
    )

    class Meta:
        abstract = True


class NFCTag(AbstractIntegerNFCTag):
    class Meta(AbstractIntegerNFCTag.Meta):
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
            )
        ]
