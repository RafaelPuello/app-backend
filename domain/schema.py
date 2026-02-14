from typing import Optional
import uuid

from ninja import Schema


class NFCTagRegisterIn(Schema):
    """Used only when registering a tag by chip UID."""
    uid: str


class NFCTagScanIn(Schema):
    """Used to resolve a tag from the NFC ASCII mirror (UID+counter string)."""
    ascii_mirror: str


class NFCTagUpdateIn(Schema):
    """
    Only include fields that are actually editable by clients.
    Add/remove fields here as your model allows.
    """
    label: Optional[str] = None


class NFCTagOut(Schema):
    """
    Minimal, privacy-safe outward schema.
    Add fields (e.g., uid, active, label) if you want them exposed.
    """
    uuid: uuid.UUID
