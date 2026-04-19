from datetime import date
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.conf import settings
from pygbif import species, occurrences

try:
    from kindwise import PlantApi, PlantIdentification, ClassificationLevel

    _KINDWISE_AVAILABLE = True
except ImportError:
    _KINDWISE_AVAILABLE = False

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
            identifier, limit=occurrence_limit, fields=occurrence_fields
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
        "numWithMedia": sum(1 for o in occurrences_list if o.get("media")),
    }

    return {
        "details": details,
        "occurrences": occurrences_list,
        "summary": summary,
    }


_GBIF_SEARCH_CACHE_TIMEOUT = 3600  # 1 hour


def search_gbif(
    query: str,
    family: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Search GBIF for species matching `query`, with optional family filter.

    Results are cached for 1 hour using Django's cache framework. The cache key
    encodes all parameters so distinct queries never share cached data.

    Args:
        query: Free-text species search term (required).
        family: Taxonomic family filter (optional, e.g. "Araceae").
        limit: Maximum number of results to return (default 20, max 100).
        offset: Zero-based result offset for pagination (default 0).

    Returns:
        Dict with keys: count, limit, offset, results (list of species dicts).
        Each result dict includes: usageKey, scientificName, canonicalName,
        rank, kingdom, phylum, class, order, family, genus, commonNames.

    Raises:
        GBIFError: If the pygbif call fails for any reason.
    """
    cache_key = f"gbif_search:{query}:{family}:{limit}:{offset}"

    def _fetch() -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "q": query,
            "limit": limit,
            "offset": offset,
        }
        if family is not None:
            kwargs["family"] = family

        try:
            raw: Dict[str, Any] = species.search(**kwargs)
        except Exception as exc:
            raise GBIFError("Error searching GBIF") from exc

        raw_results: List[Dict[str, Any]] = raw.get("results", []) or []
        normalized: List[Dict[str, Any]] = [
            _normalize_search_result(r) for r in raw_results
        ]

        return {
            "count": raw.get("count", 0),
            "limit": raw.get("limit", limit),
            "offset": raw.get("offset", offset),
            "results": normalized,
        }

    result: Dict[str, Any] = cache.get_or_set(
        cache_key, _fetch, _GBIF_SEARCH_CACHE_TIMEOUT
    )
    return result


def _normalize_search_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a single GBIF search result dict to match GBIFSearchResultOut.

    Extracts vernacular names from the nested vernacularNames list and flattens
    them into a plain list of strings under ``commonNames``.
    """
    vernacular: List[Dict[str, Any]] = raw.get("vernacularNames", []) or []
    common_names: List[str] = [
        v["vernacularName"] for v in vernacular if v.get("vernacularName")
    ]

    return {
        "usageKey": raw["usageKey"],
        "scientificName": raw.get("scientificName"),
        "canonicalName": raw.get("canonicalName"),
        "rank": raw.get("rank"),
        "kingdom": raw.get("kingdom"),
        "phylum": raw.get("phylum"),
        "class": raw.get("class"),
        "order": raw.get("order"),
        "family": raw.get("family"),
        "genus": raw.get("genus"),
        "commonNames": common_names,
    }


def search_gbif_species(
    q: str,
    family: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Search GBIF for plant species matching ``q``, with optional family filter.

    Public alias for :func:`search_gbif` using the ``q`` parameter name that
    matches the GBIF API convention and the Pokedex frontend contract.

    Results are cached for 1 hour using Django's cache framework.

    Args:
        q: Free-text species search term (scientific or common name).
        family: Taxonomic family filter (optional, e.g. "Solanaceae").
        limit: Maximum results to return (default 20, max 100).
        offset: Zero-based pagination offset (default 0).

    Returns:
        Dict with keys: count, limit, offset, results (list of species dicts).

    Raises:
        GBIFError: If the pygbif call fails for any reason.
    """
    return search_gbif(query=q, family=family, limit=limit, offset=offset)


def create_plant_from_gbif(
    user: Any,
    gbif_id: int,
    acquisition_date: Optional[str] = None,
    location: Optional[str] = None,
    notes: Optional[str] = None,
) -> Any:
    """
    Fetch GBIF species data and create a user-scoped Plant record.

    Args:
        user: Authenticated Django User who will own the plant.
        gbif_id: GBIF usage key for the species.
        acquisition_date: Optional ISO date string (YYYY-MM-DD).
        location: Optional location string. Defaults to empty string.
        notes: Optional free-form notes. Defaults to empty string.

    Returns:
        The newly created Plant instance.

    Raises:
        GBIFNotFound: If the GBIF species cannot be found.
        GBIFError: If the GBIF API call fails.
        ValueError: If acquisition_date is provided but not a valid ISO date.
    """
    # Import here to avoid circular imports at module level
    from botany.models import Plant

    details = get_plant_details(str(gbif_id))

    # Resolve name: prefer canonicalName, fall back to scientificName
    name: str = details.get("canonicalName") or details.get("scientificName") or ""
    if not name:
        raise GBIFNotFound("Plant not found")

    parsed_date: Optional[date] = None
    if acquisition_date is not None:
        try:
            parsed_date = date.fromisoformat(acquisition_date)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid acquisition_date: {acquisition_date!r}") from exc

    plant = Plant.objects.create(
        user=user,
        name=name,
        gbif_id=gbif_id,
        acquisition_date=parsed_date,
        location=location or "",
        notes=notes or "",
    )
    return plant


def plant_to_dict(plant: Any) -> Dict[str, Any]:
    """
    Serialize a Plant instance to a dictionary for API responses.

    Args:
        plant: A Plant model instance.

    Returns:
        Dictionary with plant fields suitable for PlantOut schema.
    """
    return {
        "uuid": plant.uuid,
        "name": plant.name,
        "gbif_id": plant.gbif_id,
        "description": plant.description,
        "acquisition_date": plant.acquisition_date,
        "location": plant.location,
        "notes": plant.notes,
        "created_at": plant.created_at,
        "updated_at": plant.updated_at,
    }


class KindwiseService:
    def __init__(self):
        if not _KINDWISE_AVAILABLE:
            raise ImportError(
                "kindwise package is required for plant identification. "
                "Install it with: pip install kindwise"
            )
        self.api_key = settings.KINDWISE_API_KEY
        self.api = PlantApi(api_key=self.api_key)

        # specify up to 3 languages
        self.language = ["en"]
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
                classification_level=self.classification_level,
            )
            return self.parse_identification(identification)
        except Exception as e:
            raise e

    def parse_identification(self, identification):
        probability_is_plant = identification.result.is_plant.probability

        payload = {
            "access_token": identification.access_token,
            "latitude": identification.input.latitude,
            "longitude": identification.input.longitude,
            "datetime": identification.input.datetime,
            "probability_is_plant": probability_is_plant,
        }

        # if probability_is_plant < 0.5:
        #     return payload

        payload.update(
            self.parse_suggestions(identification.result.classification.suggestions)
        )  # noqa: E501
        return payload

    def parse_suggestions(self, suggestions):
        top_match = suggestions[0]
        return {
            "suggestions": {
                index: {
                    "id": value.details["gbif_id"],
                    "name": value.name,
                    "probability": value.probability,
                }
                for index, value in enumerate(suggestions)
            },
            "top_match_id": top_match.details["gbif_id"],
            "top_match_name": top_match.name,
            "top_match_probability": top_match.probability,
        }

    def get_details(self):
        return ["gbif_id"]
