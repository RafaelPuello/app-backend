from datetime import datetime
from typing import Any, Dict, List, Optional

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
        "populate_by_name": True,   # accept both class_ and class
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
