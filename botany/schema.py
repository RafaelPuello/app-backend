from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from ninja import Schema, Field


class ErrorOut(Schema):
    error: str = Field(..., description="Human-readable error message")


class PlantDetailOut(Schema):
    key: int
    nubKey: Optional[int] = None
    nameKey: Optional[int] = None
    taxonID: Optional[str] = None

    kingdom: Optional[str] = None
    phylum: Optional[str] = None
    order: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None

    # In Pydantic v2, alias must be set using Field(..., alias="class")
    class_: Optional[str] = Field(default=None, alias="class")

    kingdomKey: Optional[int] = None
    phylumKey: Optional[int] = None
    classKey: Optional[int] = None
    orderKey: Optional[int] = None
    familyKey: Optional[int] = None
    genusKey: Optional[int] = None

    datasetKey: Optional[str] = None
    constituentKey: Optional[str] = None
    parentKey: Optional[int] = None
    parent: Optional[str] = None

    scientificName: Optional[str] = None
    canonicalName: Optional[str] = None
    authorship: Optional[str] = None

    nameType: Optional[str] = None
    rank: Optional[str] = None
    origin: Optional[str] = None
    taxonomicStatus: Optional[str] = None

    nomenclaturalStatus: Optional[List[str]] = None
    remarks: Optional[str] = None

    publishedIn: Optional[str] = None
    numDescendants: Optional[int] = None

    lastCrawled: Optional[datetime] = None
    lastInterpreted: Optional[datetime] = None

    issues: Optional[List[str]] = None

    # Pydantic v2 configuration
    model_config = {
        "populate_by_name": True,  # accept both class_ and class
        "alias_generator": None,
        "protected_namespaces": (),  # required by Ninja in some cases
    }


class PlantOccurrenceOut(Schema):
    name: Optional[str] = None
    license: Optional[str] = None
    month: Optional[int] = None
    year: Optional[int] = None
    eventDate: Optional[str] = None
    media: Optional[List[Dict[str, Any]]] = None


class GBIFSearchResultOut(Schema):
    """A single species result from the GBIF species search API."""

    usageKey: int
    scientificName: Optional[str] = None
    canonicalName: Optional[str] = None
    rank: Optional[str] = None
    kingdom: Optional[str] = None
    phylum: Optional[str] = None
    class_: Optional[str] = Field(default=None, alias="class")
    order: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None
    commonNames: List[str] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
        "alias_generator": None,
        "protected_namespaces": (),
    }


class GBIFSearchPaginatedOut(Schema):
    """Paginated wrapper for GBIF species search results."""

    count: int
    limit: int
    offset: int
    results: List[GBIFSearchResultOut]


class CreatePlantFromGBIFIn(Schema):
    """Input schema for creating a Plant record from a GBIF species."""

    gbif_id: int = Field(..., description="GBIF usage key for the species")
    acquisition_date: Optional[str] = Field(
        default=None, description="ISO date string (YYYY-MM-DD) when the plant was acquired"
    )
    location: Optional[str] = Field(
        default=None, description="Where this plant is kept (e.g. 'Living room')"
    )
    notes: Optional[str] = Field(
        default=None, description="Free-form notes about this plant"
    )


class PlantCreateFromGBIFIn(Schema):
    """Request body for creating a Plant from GBIF data (user-supplied name)."""

    gbif_id: int = Field(..., description="GBIF usage key (species ID)")
    name: str = Field(..., description="Plant name (scientific or common)")
    acquisition_date: Optional[date] = Field(
        default=None, description="Date when the plant was acquired"
    )
    location: Optional[str] = Field(
        default=None, description="Where this plant is kept (e.g. 'Nursery')"
    )
    notes: Optional[str] = Field(
        default=None, description="Free-form notes about this plant"
    )


class PlantOut(Schema):
    """Output schema for a Plant record."""

    uuid: UUID
    name: str
    gbif_id: Optional[int] = None
    description: str
    acquisition_date: Optional[date] = None
    location: str
    notes: str
    created_at: datetime
    updated_at: datetime
