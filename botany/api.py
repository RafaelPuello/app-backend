from typing import List, Optional

from ninja import Query
from ninja.errors import HttpError
from ninja_extra import (
    ControllerBase,
    api_controller,
    http_get,
    http_post,
)
from ninja_extra.pagination import (
    LimitOffsetPagination,
    NinjaPaginationResponseSchema,
    paginate,
)

from config.auth import JWTAuthenticationBackend
from .schema import (
    CreatePlantFromGBIFIn,
    ErrorOut,
    GBIFSearchPaginatedOut,
    PlantDetailOut,
    PlantOccurrenceOut,
    PlantOut,
)
from .services import (
    GBIFError,
    GBIFNotFound,
    create_plant_from_gbif,
    get_plant_details,
    get_plant_occurrences,
    plant_to_dict,
    search_gbif,
    search_gbif_species,
)


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

    @http_post(
        "/from-gbif",
        response={201: PlantOut, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
        summary="Create a Plant record from a GBIF species (requires authentication)",
        auth=JWTAuthenticationBackend(),
    )
    def create_plant_from_gbif_endpoint(self, payload: CreatePlantFromGBIFIn):
        """
        Create a user-scoped Plant record by fetching species data from GBIF.

        Requires a valid JWT Bearer token. The plant is scoped to the
        authenticated user and cannot be accessed by other users.

        Returns HTTP 201 on success, 401 if not authenticated, 404 if the
        GBIF species is not found, or 400 if acquisition_date is invalid.
        """
        user = self.context.request.user
        try:
            plant = create_plant_from_gbif(
                user=user,
                gbif_id=payload.gbif_id,
                acquisition_date=payload.acquisition_date,
                location=payload.location,
                notes=payload.notes,
            )
        except GBIFNotFound as exc:
            raise HttpError(404, str(exc))
        except GBIFError as exc:
            raise HttpError(500, str(exc))
        except ValueError as exc:
            raise HttpError(400, str(exc))

        return 201, plant_to_dict(plant)

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


@api_controller("/plants", tags=["Plants"])
class PlantSearchController(ControllerBase):
    """
    Plant discovery endpoints for the Pokedex feature.

    Provides GBIF species search for the frontend plant catalog grid.
    All endpoints are public (no authentication required).
    """

    @http_get(
        "/search-gbif/",
        response={200: GBIFSearchPaginatedOut, 500: ErrorOut},
        summary="Search GBIF for plant species by name (public)",
        auth=None,
    )
    def search_gbif_endpoint(
        self,
        q: str,
        family: Optional[str] = None,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> GBIFSearchPaginatedOut:
        """
        Search the GBIF backbone taxonomy for plant species matching the given query.

        Results are cached for 1 hour. No authentication is required.

        Args:
            q: Search query (scientific or common name, required).
            family: Optional taxonomic family filter (e.g. "Solanaceae").
            limit: Results per page (default 20, max 100).
            offset: Pagination offset (default 0).

        Returns:
            GBIFSearchPaginatedOut with count, limit, offset, and paginated results.
        """
        try:
            data = search_gbif_species(q=q, family=family, limit=limit, offset=offset)
        except GBIFError as exc:
            raise HttpError(500, str(exc))
        return GBIFSearchPaginatedOut(**data)
