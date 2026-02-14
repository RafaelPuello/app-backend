from typing import Any, Dict, List, Optional

from django.conf import settings
from kindwise import PlantApi, PlantIdentification, ClassificationLevel
from pygbif import species, occurrences

from .utils import resolve_gbif_id

# Domain-specific exceptions so callers don't need to import pygbif or know implementation details.
class GBIFNotFound(Exception):
    """Raised when the requested GBIF resource or results are not found (404-like)."""
    pass

class GBIFError(Exception):
    """Raised when something goes wrong calling GBIF (500-like)."""
    pass


def get_plant_details(identifier: str) -> Dict[str, Any]:
    """
    Resolve `identifier` to a GBIF id and fetch the plant details via pygbif.species.name_usage.

    Raises:
        GBIFNotFound: if identifier cannot be resolved to a GBIF id.
        GBIFError: on network/API errors from pygbif.
    Returns:
        The raw dict returned by pygbif.species.name_usage
    """
    gbif_id = resolve_gbif_id(identifier)
    if gbif_id is None:
        raise GBIFNotFound("Plant not found")

    try:
        details: Dict[str, Any] = species.name_usage(key=gbif_id, data="all", limit=1)
    except Exception as exc:
        # wrap implementation-specific exceptions so the controller can map them to HTTP 500
        raise GBIFError("Error accessing GBIF API") from exc

    return details


def get_plant_occurrences(
    identifier: str,
    limit: int = 300,
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Resolve `identifier` and return a list of occurrences (already filtered).

    Raises:
        GBIFNotFound: if identifier cannot be resolved or no occurrences found.
        GBIFError: on network/API errors from pygbif.
    Returns:
        List of occurrence dicts (results)
    """
    gbif_id = resolve_gbif_id(identifier)
    if gbif_id is None:
        raise GBIFNotFound("Plant not found")

    fields = fields or ["name", "media", "license", "month", "year", "eventDate"]

    try:
        occ_data: Dict[str, Any] = occurrences.search(
            taxon_key=gbif_id,
            has_coordinate=True,
            has_geospatial_issue=False,
            mediatype="StillImage",
            fields=fields,
            limit=limit,
        )
    except Exception as exc:
        raise GBIFError("Error retrieving occurrences from GBIF API") from exc

    results: List[Dict[str, Any]] = occ_data.get("results", []) or []
    if not results:
        # intentionally using NotFound semantics for empty results
        raise GBIFNotFound("No occurrences found")

    return results


def get_plant_summary(
    identifier: str,
    occurrence_limit: int = 300,
    occurrence_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Fetch a combined summary for a plant: high-level taxon details + image occurrences.

    Raises:
        GBIFNotFound: if the identifier cannot be resolved, plant does not exist,
                      or occurrences are empty.
        GBIFError: if any pygbif operation fails.
    Returns:
        {
            "details": {...},          # name_usage data
            "occurrences": [...],      # StillImage occurrences
            "summary": {...}           # lightweight derived info
        }
    """
    # --- Fetch details ---
    details = get_plant_details(identifier)

    # --- Fetch occurrences ---
    try:
        occurrences_list = get_plant_occurrences(
            identifier,
            limit=occurrence_limit,
            fields=occurrence_fields
        )
    except GBIFNotFound:
        # Depending on business logic, we can choose to allow empty,
        # but right now we follow your stricter contract.
        raise

    # --- Compute light derived summary ---
    summary: Dict[str, Any] = {
        "scientificName": details.get("scientificName"),
        "canonicalName": details.get("canonicalName"),
        "rank": details.get("rank"),
        "kingdom": details.get("kingdom"),
        "phylum": details.get("phylum"),
        "family": details.get("family"),
        "genus": details.get("genus"),
        "usageKey": details.get("usageKey"),
        "numOccurrences": len(occurrences_list),
        "numWithMedia": sum(1 for o in occurrences_list if o.get("media"))
    }

    return {
        "details": details,
        "occurrences": occurrences_list,
        "summary": summary,
    }


class KindwiseService:
    def __init__(self):
        self.api_key = settings.KINDWISE_API_KEY
        self.api = PlantApi(api_key=self.api_key)

        # specify up to 3 languages
        self.language = ['en']
        self.details = self.get_details()
        # self.health = 'all'
        self.classification_level = ClassificationLevel.SPECIES

    def identify_plant(self, images, coordinates=None):
        try:
            identification: PlantIdentification = self.api.identify(
                images,
                latitude_longitude=coordinates,
                language=self.language,
                details=self.details,
                # health=self.health,
                classification_level=self.classification_level
            )
            return self.parse_identification(identification)
        except Exception as e:
            raise e

    def parse_identification(self, identification):
        probability_is_plant = identification.result.is_plant.probability

        payload = {
            'access_token': identification.access_token,
            'latitude': identification.input.latitude,
            'longitude': identification.input.longitude,
            'datetime': identification.input.datetime,
            'probability_is_plant': probability_is_plant,
        }

        # if probability_is_plant < 0.5:
        #     return payload

        payload.update(self.parse_suggestions(identification.result.classification.suggestions))  # noqa: E501
        return payload

    def parse_suggestions(self, suggestions):
        top_match = suggestions[0]
        return {
            'suggestions': {
                index: {
                    'id': value.details['gbif_id'],
                    'name': value.name,
                    'probability': value.probability,
                } for index, value in enumerate(suggestions)
            },
            'top_match_id': top_match.details['gbif_id'],
            'top_match_name': top_match.name,
            'top_match_probability': top_match.probability,
        }

    def get_details(self):
        return ['gbif_id']
