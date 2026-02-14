from typing import Optional
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth.models import AbstractBaseUser
from django.utils.translation import gettext_lazy as _

from nfctags import get_nfctag_model
from nfctags.models import AbstractNFCTag

NFCTag = get_nfctag_model()


class NFCTagService:
    """
    Service layer for managing NFC tags and their content.
    """
    def __init__(self, user: Optional[AbstractBaseUser] = None):
        self.user = user

    @transaction.atomic
    def create_tag(self, uid: str) -> AbstractNFCTag:
        """
        Create a new NFCTag instance.
        """
        tag = NFCTag(uid=uid, user=self.user)
        tag.full_clean()
        tag.save()
        return tag

    @transaction.atomic
    def register_user(self, tag: AbstractNFCTag) -> AbstractNFCTag:
        """
        Attach a user to an existing NFCTag (if not already registered).
        """
        if not tag.is_available_to_register:
            raise ValidationError(f"Tag {tag.uid} is already registered.")
        tag.user = self.user
        tag.full_clean()
        tag.save()
        return tag

    @transaction.atomic
    def disconnect_tag(self, tag: AbstractNFCTag) -> AbstractNFCTag:
        if tag.user != self.user:
            raise ValidationError(_('This tag is not registered to your account.'))
        tag.user = None
        tag.full_clean()
        tag.save()
        return tag

    @transaction.atomic
    def deactivate_tag(self, tag: AbstractNFCTag) -> AbstractNFCTag:
        """
        Deactivate an NFCTag by setting active=False.
        """
        tag.active = False
        tag.full_clean()
        tag.save()
        return tag
