from datetime import datetime
from typing import Optional
from uuid import UUID

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

    uuid: UUID


# ---------------------------------------------------------------------------
# NFC Tag ↔ Plant binding schemas
# ---------------------------------------------------------------------------


class PlantOutNested(Schema):
    """Nested plant info embedded in NFC tag responses."""

    id: UUID
    name: str
    species: Optional[str] = None

    class Config:
        from_attributes = True


class BindPlantRequest(Schema):
    """Request body for binding an NFC tag to a plant."""

    plant_id: UUID


class PlantLabelOut(Schema):
    """NFC PlantLabel detail with optional plant binding.

    Uses ``uuid`` as the tag identifier and ``plant_id`` (the plant's UUID,
    not its database PK) for the foreign-key reference.
    """

    uuid: UUID
    plant_id: Optional[UUID] = None
    plant: Optional[PlantOutNested] = None
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @staticmethod
    def resolve_plant_id(obj: object) -> Optional[UUID]:
        """Return the plant's *public* UUID (not the integer PK)."""
        plant = getattr(obj, "plant", None)
        if plant is None:
            return None
        return plant.uuid

    @staticmethod
    def resolve_plant(obj: object) -> Optional[PlantOutNested]:
        """Return nested plant data, or None when unbound."""
        plant = getattr(obj, "plant", None)
        if plant is None:
            return None
        return PlantOutNested(id=plant.uuid, name=plant.name, species=None)
