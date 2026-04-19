from typing import List, Optional

from ninja import Query
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

from .schema import (
    ErrorOut,
    GBIFSearchPaginatedOut,
    PlantDetailOut,
    PlantOccurrenceOut,
)
from .services import GBIFError, GBIFNotFound, get_plant_details, get_plant_occurrences, search_gbif


@api_controller("/gbif", tags=["GBIF (Plants)"])
class GBIFController(ControllerBase):
    """
    Endpoints that proxy/normalize GBIF data for the frontend.
    """

    @http_get(
        "/search/",
        response={200: GBIFSearchPaginatedOut, 500: ErrorOut},
        summary="Search GBIF species by name with optional family filter (public)",
        auth=None,
    )
    def search_species(
        self,
        q: str,
        family: Optional[str] = None,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> GBIFSearchPaginatedOut:
        """
        Search the GBIF backbone taxonomy for species matching the given query.

        Results are cached for 1 hour. No authentication is required.
        """
        try:
            data = search_gbif(query=q, family=family, limit=limit, offset=offset)
        except GBIFError as exc:
            raise HttpError(500, str(exc))
        return GBIFSearchPaginatedOut(**data)

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
        response={
            200: NinjaPaginationResponseSchema[PlantOccurrenceOut],
            404: ErrorOut,
            500: ErrorOut,
        },
        summary="Paginated occurrences for a plant",
    )
    @paginate(LimitOffsetPagination)
    def list_plant_occurrences(self, identifier: str):
        try:
            results = get_plant_occurrences(identifier)
        except GBIFNotFound as exc:
            raise HttpError(404, str(exc))
        except GBIFError as exc:
            raise HttpError(500, str(exc))

        return results
