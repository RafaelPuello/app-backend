from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from ninja.errors import HttpError

from config.auth import JWTAuthenticationBackend
from ninja_extra import (
    api_controller,
    ControllerBase,
    http_delete,
    http_get,
    http_post,
    http_put,
)
from ninja_extra.pagination import (
    LimitOffsetPagination,
    NinjaPaginationResponseSchema,
    paginate
)
from ninja_extra.permissions import IsAuthenticated

from nfctags import get_nfctag_model
from .schema import NFCTagOut, NFCTagRegisterIn, NFCTagScanIn, NFCTagUpdateIn
from .selectors import get_nfctag_by_scan, get_nfctags_for, get_nfctags_visible_for
from .services import NFCTagService


NFCTag = get_nfctag_model()


@api_controller(
    "/nfctags",
    permissions=[IsAuthenticated],
    auth=[JWTAuthenticationBackend()],
    tags=["App Domain - NFC Tags"],
)
class DomainController(ControllerBase):
    """
    Parity with the Django views:
    - All queries are user-scoped via selectors
    - Mutations go through NFCTagService
    """

    @http_get("", response=NinjaPaginationResponseSchema[NFCTagOut])
    @paginate(LimitOffsetPagination)
    def list_tags(self):
        user = self.context.request.user
        return get_nfctags_for(fetched_by=user).order_by("-uuid")

    @http_get("/{uuid:nfctag_uuid}", response=NFCTagOut)
    def retrieve(self, nfctag_uuid):
        user = self.context.request.user
        qs = get_nfctags_for(fetched_by=user)
        return get_object_or_404(qs, uuid=nfctag_uuid)

    @http_post("/scan", response={200: NFCTagOut, 404: dict})
    def scan_lookup(self, payload: NFCTagScanIn):
        """
        Resolve a tag from the ASCII mirror (UID+counter).
        """
        user = self.context.request.user
        tag = get_nfctag_by_scan(ascii_mirror=payload.ascii_mirror, user=user)
        if not tag:
            return 404, {"detail": "Tag not found"}

        visible_ids = set(get_nfctags_visible_for(user=user))
        if tag.id not in visible_ids:
            return 404, {"detail": "Tag not found"}

        return tag

    @http_post("/register", response={201: NFCTagOut, 200: NFCTagOut, 409: dict})
    def register(self, payload: NFCTagRegisterIn):
        """
        Register a tag to the current user by UID.
        - 201 if created & attached
        - 200 if existed and (now) attached to this user
        - 409 if exists and owned by someone else
        """
        user = self.context.request.user
        service = NFCTagService(user=user)

        tag = NFCTag.objects.filter(uid=payload.uid).first()
        if tag is None:
            tag = service.create_tag(uid=payload.uid)
            return 201, tag

        try:
            if getattr(tag, "is_available_to_register", False):
                tag = service.register_user(tag=tag)
                return 200, tag
            return 409, {"detail": "This tag is already registered to another account."}
        except ValidationError as e:
            raise HttpError(400, str(e))

    @http_put("/{uuid:nfctag_uuid}", response=NFCTagOut)
    def update(self, nfctag_uuid, payload: NFCTagUpdateIn):
        """
        Update only explicitly allowed fields (e.g., label).
        UID is immutable.
        """
        user = self.context.request.user
        tag = get_object_or_404(get_nfctags_for(fetched_by=user), uuid=nfctag_uuid)

        dirty_fields: list[str] = []

        if payload.label is not None and hasattr(tag, "label"):
            tag.label = payload.label
            dirty_fields.append("label")

        if dirty_fields:
            tag.full_clean()
            tag.save(update_fields=dirty_fields)

        return tag

    @http_post("/{uuid:nfctag_uuid}/disconnect", response={200: NFCTagOut, 400: dict})
    def disconnect(self, nfctag_uuid):
        """
        Mirrors the view 'disconnect' by clearing ownership.
        """
        user = self.context.request.user
        tag = get_object_or_404(get_nfctags_for(fetched_by=user), uuid=nfctag_uuid)
        service = NFCTagService(user=user)
        try:
            tag = service.disconnect_tag(tag)
            return 200, tag
        except ValidationError as e:
            return 400, {"detail": str(e)}

    @http_post("/{uuid:nfctag_uuid}/deactivate", response=NFCTagOut)
    def deactivate(self, nfctag_uuid):
        """
        Sets active=False via the service.
        """
        user = self.context.request.user
        tag = get_object_or_404(get_nfctags_for(fetched_by=user), uuid=nfctag_uuid)
        service = NFCTagService(user=user)
        return service.deactivate_tag(tag)

    @http_delete("/{uuid:nfctag_uuid}", response={200: dict, 400: dict})
    def delete(self, nfctag_uuid):
        """
        Prefer 'disconnect' over delete; this is a hard delete.
        """
        user = self.context.request.user
        tag = get_object_or_404(get_nfctags_for(fetched_by=user), uuid=nfctag_uuid)
        try:
            tag.delete()
            return 200, {"success": True}
        except Exception as e:
            return 400, {"detail": str(e)}
