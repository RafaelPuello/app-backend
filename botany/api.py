from typing import Any, Dict, List

from ninja.errors import HttpError
from ninja_extra import (
    ControllerBase,
    api_controller,
    http_get,
)
from ninja_extra.pagination import (
    LimitOffsetPagination,
    NinjaPaginationResponseSchema,
    paginate,
)
from pygbif import species, occurrences

from .schema import (
    ErrorOut,
    PlantDetailOut,
    PlantOccurrenceOut,
)
from .services import GBIFNotFound, GBIFError, get_plant_details
from .utils import resolve_gbif_id


@api_controller('/gbif', tags=['GBIF (Plants)'])
class GBIFController(ControllerBase):
    """
    Endpoints that proxy/normalize GBIF data for the frontend.
    """
    @http_get(
        "/{str:identifier}",
        response={200: PlantDetailOut, 404: ErrorOut, 500: ErrorOut},
        summary="Fetch plant details from GBIF by id/slug/uuid/name",
    )
    def retrieve_plant_details(self, identifier: str):
        try:
            plant = get_plant_details(identifier)
        except GBIFNotFound as e:
            raise HttpError(404, str(e))
        except GBIFError as e:
            raise HttpError(500, str(e))
        return plant

    @http_get(
        "/{str:identifier}/occurrences",
        response={200: NinjaPaginationResponseSchema[PlantOccurrenceOut], 404: ErrorOut, 500: ErrorOut},
        summary="Paginated occurrences for a plant",
    )
    @paginate(LimitOffsetPagination)
    def list_plant_occurrences(self, identifier: str):
        gbif_id = resolve_gbif_id(identifier)
        if gbif_id is None:
            raise HttpError(404, "Plant not found")

        try:
            occ_data: Dict[str, Any] = occurrences.search(
                taxon_key=gbif_id,
                has_coordinate=True,
                has_geospatial_issue=False,
                mediatype="StillImage",
                fields=["name", "media", "license", "month", "year", "eventDate"],
                limit=300,
            )
        except Exception:
            raise HttpError(500, "Error retrieving occurrences from GBIF API")

        results: List[Dict[str, Any]] = occ_data.get("results", []) or []
        if not results:
            raise HttpError(404, "No occurrences found")

        return results
