from typing import Iterable, Optional
from django.db.models import Q
from django.contrib.auth.models import AbstractBaseUser

from nfctags import get_nfctag_model
from nfctags.models import AbstractNFCTag
from nfctags.validators import parse_ascii_mirror

NFCTag = get_nfctag_model()


def get_nfctag_by_scan(*, ascii_mirror: str, user: Optional[AbstractBaseUser] = None) -> Optional[NFCTag]:
    """
    Returns the NFCTag object corresponding to the given NFC tag scan.

    The function parses the ASCII mirror (UID + counter) of the scanned tag
    and attempts to retrieve the NFCTag instance from the database.

    Args:
        ascii_mirror (str): The ASCII mirror string containing the NFC tag UID and scan counter.
        user (Optional[AbstractBaseUser]): The user performing the scan. If provided,
            you can add additional filtering logic (e.g., ownership, permissions).

    Returns:
        Optional[NFCTag]: The NFCTag object if it exists; otherwise, None.
    """
    uid, counter = parse_ascii_mirror(ascii_mirror)

    try:
        nfctag = NFCTag.objects.get(uid=uid)
        # (Optional future check: If user is provided, enforce ownership)
        # if user and nfctag.user != user:
        #     return None
        return nfctag
    except NFCTag.DoesNotExist:
        return None


def get_nfctags_visible_for(*, user: AbstractBaseUser) -> Iterable[int]:
    """
    Returns a list of nfctag IDs that are visible to the given user.
    """
    if not user.is_authenticated:
        return []
    return NFCTag.objects.filter(
        user=user,
        active=True,
    ).values_list('id', flat=True)


def get_nfctags_for(*, fetched_by: AbstractBaseUser) -> Iterable[AbstractNFCTag]:
    query = Q(id__in=get_nfctags_visible_for(user=fetched_by))
    return NFCTag.objects.filter(query)
