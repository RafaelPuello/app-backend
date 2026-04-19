"""
QA2: API Contract Validation — Pokedex MVP

Validates that all Pokedex-related API endpoints return correct response schemas,
status codes, and error handling as defined in the API specification.

Endpoints tested:
- GET  /app/api/plants/search-gbif/           — GBIF species search (public)
- POST /app/api/plants/from-gbif/             — Create plant from GBIF (auth required)
- POST /app/api/plants/{uuid}/bind-nfc/       — Bind NFC tag to plant (auth required)
- POST /app/api/plants/{uuid}/unbind-nfc/     — Unbind NFC tag from plant (auth required)

Run:
    DJANGO_SETTINGS_MODULE=config.settings_test pytest botany/tests/test_api_contracts.py -v

Authentication pattern:
    The app backend uses two-layer auth for JWT-protected endpoints:
    1. Django session (client.login) populates request.user via session middleware.
    2. JWT Bearer header satisfies the Ninja endpoint auth= guard.
    Both are required: controllers read self.context.request.user (session-based)
    while the guard validates the JWT token. Mirrors botany/test_api.py convention.

Note: JWT-authenticated tests skip automatically when the ID service private
key is absent (CI / environments without the id/ submodule checked out).
"""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


# ---------------------------------------------------------------------------
# JWT + session auth helpers
# ---------------------------------------------------------------------------


def _create_test_jwt(user):
    """
    Mint an RS256 JWT for ``user`` using the ID service private key.

    Skips the calling test if the key file is not found.
    """
    import jwt

    private_key_path = (
        Path(__file__).resolve().parents[4]
        / "id"
        / "backend"
        / "config"
        / "keys"
        / "jwt_private_key.pem"
    )
    try:
        private_key = private_key_path.read_text()
    except FileNotFoundError:
        pytest.skip("ID service private key not found; skipping JWT-auth tests")

    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "uuid": str(user.id),
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _auth_header(user) -> str:
    return f"Bearer {_create_test_jwt(user)}"


def _make_user(suffix: str):
    return User.objects.create_user(
        username=f"contract_user_{suffix}",
        email=f"contract_{suffix}@example.com",
        password="testpass",
    )


def _auth_client(client, user) -> dict:
    """
    Authenticate the Django test client for JWT-protected endpoints.

    The app backend uses two-layer auth:
    1. Django session (via client.login) populates request.user through middleware.
    2. JWT Bearer header satisfies the ninja endpoint auth= guard.

    Both are required because the controllers read `self.context.request.user`
    (populated by session middleware) while the JWT backend validates the token
    for the endpoint guard. This pattern mirrors the established convention in
    botany/test_api.py.

    Returns a dict suitable for use as **kwargs to client.get/post.
    """
    client.login(username=user.username, password="testpass")
    return {"HTTP_AUTHORIZATION": _auth_header(user)}


# ---------------------------------------------------------------------------
# Mock GBIF response re-used across tests
# ---------------------------------------------------------------------------

_MOCK_GBIF_SEARCH = {
    "offset": 0,
    "limit": 20,
    "endOfRecords": False,
    "count": 42,
    "results": [
        {
            "usageKey": 5289683,
            "scientificName": "Solanum lycopersicum L.",
            "canonicalName": "Solanum lycopersicum",
            "rank": "SPECIES",
            "kingdom": "Plantae",
            "phylum": "Tracheophyta",
            "class": "Magnoliopsida",
            "order": "Solanales",
            "family": "Solanaceae",
            "genus": "Solanum",
            "vernacularNames": [
                {"vernacularName": "tomato", "language": "eng"},
            ],
        },
    ],
}


# ===========================================================================
# GET /app/api/plants/search-gbif/
# ===========================================================================


@pytest.mark.django_db
class TestGBIFSearchContract:
    """Verify /app/api/plants/search-gbif/ response schema and error codes."""

    def test_returns_200_with_valid_q_param(self, client):
        """GET /app/api/plants/search-gbif/?q=tomato returns HTTP 200."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = _MOCK_GBIF_SEARCH
            response = client.get("/app/api/plants/search-gbif/?q=tomato")
        assert response.status_code == 200

    def test_response_schema_has_required_top_level_fields(self, client):
        """Response contains count, limit, offset, and results fields."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = _MOCK_GBIF_SEARCH
            response = client.get("/app/api/plants/search-gbif/?q=tomato")

        data = response.json()
        for field in ("count", "limit", "offset", "results"):
            assert field in data, f"Response missing required field: {field}"

    def test_response_schema_field_types(self, client):
        """count/limit/offset are ints; results is a list."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = _MOCK_GBIF_SEARCH
            response = client.get("/app/api/plants/search-gbif/?q=tomato")

        data = response.json()
        assert isinstance(data["count"], int)
        assert isinstance(data["limit"], int)
        assert isinstance(data["offset"], int)
        assert isinstance(data["results"], list)

    def test_each_result_has_usage_key(self, client):
        """Every result in results[] contains a usageKey field."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = _MOCK_GBIF_SEARCH
            response = client.get("/app/api/plants/search-gbif/?q=tomato")

        results = response.json()["results"]
        assert len(results) > 0, "Expected at least one result in mock response"
        for result in results:
            assert "usageKey" in result, "Result missing usageKey"
            assert isinstance(result["usageKey"], int)

    def test_result_scientific_name_is_string_or_null(self, client):
        """scientificName in each result is a string or null."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = _MOCK_GBIF_SEARCH
            response = client.get("/app/api/plants/search-gbif/?q=tomato")

        for result in response.json()["results"]:
            name = result.get("scientificName")
            assert name is None or isinstance(name, str)

    def test_missing_q_param_returns_422(self, client):
        """GET without required q param returns 422 Unprocessable Entity."""
        response = client.get("/app/api/plants/search-gbif/")
        assert response.status_code == 422

    def test_pagination_limit_reflected_in_response(self, client):
        """limit query param is reflected in the response body."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = {**_MOCK_GBIF_SEARCH, "limit": 10}
            response = client.get(
                "/app/api/plants/search-gbif/?q=plant&limit=10&offset=0"
            )
        assert response.status_code == 200
        assert response.json()["limit"] == 10

    def test_pagination_offset_reflected_in_response(self, client):
        """offset query param is reflected in the response body."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = {**_MOCK_GBIF_SEARCH, "offset": 20}
            response = client.get(
                "/app/api/plants/search-gbif/?q=plant&limit=20&offset=20"
            )
        assert response.status_code == 200
        assert response.json()["offset"] == 20

    def test_endpoint_is_public_no_auth_required(self, client):
        """No Authorization header needed — endpoint returns 200 without auth."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = {
                **_MOCK_GBIF_SEARCH,
                "count": 0,
                "results": [],
            }
            # Plain client with no session or token
            response = client.get("/app/api/plants/search-gbif/?q=public")
        assert response.status_code == 200

    def test_gbif_error_returns_500(self, client):
        """When pygbif raises, endpoint returns HTTP 500."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.side_effect = Exception("GBIF unavailable")
            response = client.get("/app/api/plants/search-gbif/?q=broken")
        assert response.status_code == 500

    def test_family_filter_forwarded_to_gbif(self, client):
        """family query param is forwarded to pygbif species.search."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = _MOCK_GBIF_SEARCH
            client.get("/app/api/plants/search-gbif/?q=solanum&family=Solanaceae")

        call_kwargs = mock_species.search.call_args.kwargs
        assert call_kwargs.get("family") == "Solanaceae"


# ===========================================================================
# POST /app/api/plants/from-gbif/
# ===========================================================================


@pytest.mark.django_db
class TestCreatePlantFromGBIFContract:
    """Verify /app/api/plants/from-gbif/ response schema and error codes."""

    def test_returns_201_with_valid_data(self, client):
        """POST with valid gbif_id and name returns HTTP 201."""
        user = _make_user("create1")
        extra = _auth_client(client, user)
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"gbif_id": 5289683, "name": "Tomato"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 201

    def test_response_schema_has_required_plant_fields(self, client):
        """201 response contains all required Plant schema fields."""
        user = _make_user("create2")
        extra = _auth_client(client, user)
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps(
                {
                    "gbif_id": 5289683,
                    "name": "Solanum lycopersicum",
                    "acquisition_date": "2026-04-19",
                    "location": "Garden",
                    "notes": "Started from seed",
                }
            ),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 201
        data = response.json()

        # Required fields as per PlantOut schema
        required_fields = [
            "uuid",
            "name",
            "gbif_id",
            "description",
            "acquisition_date",
            "location",
            "notes",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in data, f"Response missing required field: {field}"

    def test_plant_data_matches_submitted_values(self, client):
        """Response data reflects the values submitted in the request."""
        user = _make_user("create3")
        extra = _auth_client(client, user)
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps(
                {
                    "gbif_id": 5289683,
                    "name": "My Tomato",
                    "acquisition_date": "2026-04-19",
                    "location": "Greenhouse",
                    "notes": "Heirloom variety",
                }
            ),
            content_type="application/json",
            **extra,
        )
        data = response.json()
        assert data["gbif_id"] == 5289683
        assert data["name"] == "My Tomato"
        assert data["acquisition_date"] == "2026-04-19"
        assert data["location"] == "Greenhouse"
        assert data["notes"] == "Heirloom variety"

    def test_plant_scoped_to_authenticated_user(self, client):
        """Created plant belongs to the authenticated user, not another."""
        user = _make_user("create4")
        extra = _auth_client(client, user)
        client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"gbif_id": 5289683, "name": "Scoped Tomato"}),
            content_type="application/json",
            **extra,
        )

        from botany.models import Plant

        plant = Plant.objects.filter(gbif_id=5289683, user=user).first()
        assert plant is not None
        assert plant.name == "Scoped Tomato"

    def test_missing_gbif_id_returns_422(self, client):
        """POST without gbif_id returns 422 Unprocessable Entity."""
        user = _make_user("create5")
        extra = _auth_client(client, user)
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"name": "No ID Plant"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 422

    def test_missing_name_returns_422(self, client):
        """POST without name returns 422 Unprocessable Entity."""
        user = _make_user("create6")
        extra = _auth_client(client, user)
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"gbif_id": 5289683}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 422

    def test_no_auth_returns_401(self, client):
        """POST without Authorization header returns 401 Unauthorized."""
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"gbif_id": 5289683, "name": "Plant"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_optional_fields_can_be_omitted(self, client):
        """POST succeeds with only required fields; optional fields default gracefully."""
        user = _make_user("create7")
        extra = _auth_client(client, user)
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"gbif_id": 2684241, "name": "Monstera"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 201
        data = response.json()
        # Optional fields should be present in response — null or empty string — not absent
        assert "acquisition_date" in data
        assert "location" in data
        assert "notes" in data

    def test_uuid_field_is_valid_uuid_format(self, client):
        """Created plant uuid is a valid UUID string."""
        import uuid

        user = _make_user("create8")
        extra = _auth_client(client, user)
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"gbif_id": 5289683, "name": "UUID Check"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 201
        data = response.json()
        assert "uuid" in data
        # Must parse without raising ValueError
        uuid.UUID(data["uuid"])


# ===========================================================================
# POST /app/api/plants/{uuid}/bind-nfc/
# ===========================================================================


@pytest.mark.django_db
class TestBindNFCContract:
    """Verify /app/api/plants/{uuid}/bind-nfc/ response schema and error codes."""

    def _create_plant(self, user, name: str = "Monstera"):
        from botany.models import Plant

        return Plant.objects.create(name=name, user=user)

    def test_bind_nfc_returns_200(self, client):
        """POST bind-nfc/ with valid data returns HTTP 200."""
        user = _make_user("bind1")
        plant = self._create_plant(user)
        extra = _auth_client(client, user)
        response = client.post(
            f"/app/api/plants/{plant.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": "04A1B2C3D4E5F6"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 200

    def test_bind_nfc_response_has_nfc_id_and_plant_uuid(self, client):
        """bind-nfc/ response contains nfc_id and plant_uuid fields."""
        user = _make_user("bind2")
        plant = self._create_plant(user)
        extra = _auth_client(client, user)
        response = client.post(
            f"/app/api/plants/{plant.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": "04B1C2D3E4F5A6"}),
            content_type="application/json",
            **extra,
        )
        data = response.json()
        assert "nfc_id" in data, "Response missing nfc_id"
        assert "plant_uuid" in data, "Response missing plant_uuid"

    def test_bind_nfc_response_values_match_request(self, client):
        """nfc_id in response equals the submitted nfc_id; plant_uuid matches the plant."""
        user = _make_user("bind3")
        plant = self._create_plant(user)
        nfc_uid = "04C1D2E3F4A5B6"
        extra = _auth_client(client, user)
        response = client.post(
            f"/app/api/plants/{plant.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": nfc_uid}),
            content_type="application/json",
            **extra,
        )
        data = response.json()
        assert data["nfc_id"] == nfc_uid
        assert data["plant_uuid"] == str(plant.uuid)

    def test_bind_nfc_creates_plant_label_in_db(self, client):
        """Successful bind creates a PlantLabel record linked to the plant."""
        from domain.models import PlantLabel

        user = _make_user("bind4")
        plant = self._create_plant(user)
        nfc_uid = "04D1E2F3A4B5C6"
        extra = _auth_client(client, user)
        client.post(
            f"/app/api/plants/{plant.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": nfc_uid}),
            content_type="application/json",
            **extra,
        )
        label = PlantLabel.objects.filter(uid=nfc_uid, user=user).first()
        assert label is not None
        assert label.plant == plant

    def test_bind_nfc_no_auth_returns_401(self, client):
        """POST bind-nfc/ without Authorization returns 401."""
        user = _make_user("bind5")
        plant = self._create_plant(user)
        response = client.post(
            f"/app/api/plants/{plant.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": "04E1F2A3B4C5D6"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_bind_nfc_other_users_plant_returns_404(self, client):
        """User cannot bind NFC to a plant they do not own — returns 404."""
        owner = _make_user("bind6a")
        requester = _make_user("bind6b")
        other_plant = self._create_plant(owner, name="Owner's Plant")
        extra = _auth_client(client, requester)
        response = client.post(
            f"/app/api/plants/{other_plant.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": "04F1A2B3C4D5E6"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 404

    def test_rebind_nfc_updates_plant_association(self, client):
        """Rebinding an already-bound NFC tag moves it to the new plant."""
        from domain.models import PlantLabel

        user = _make_user("bind7")
        plant1 = self._create_plant(user, "Plant Alpha")
        plant2 = self._create_plant(user, "Plant Beta")
        nfc_uid = "04A2B3C4D5E6F7"
        extra = _auth_client(client, user)

        # Bind to plant1
        client.post(
            f"/app/api/plants/{plant1.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": nfc_uid}),
            content_type="application/json",
            **extra,
        )

        # Rebind to plant2
        response = client.post(
            f"/app/api/plants/{plant2.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": nfc_uid}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 200
        assert response.json()["plant_uuid"] == str(plant2.uuid)

        label = PlantLabel.objects.get(uid=nfc_uid, user=user)
        assert label.plant == plant2


# ===========================================================================
# POST /app/api/plants/{uuid}/unbind-nfc/
# ===========================================================================


@pytest.mark.django_db
class TestUnbindNFCContract:
    """Verify /app/api/plants/{uuid}/unbind-nfc/ response schema and error codes."""

    def _create_plant(self, user, name: str = "Ficus"):
        from botany.models import Plant

        return Plant.objects.create(name=name, user=user)

    def _bind_label(self, user, plant, uid: str):
        from domain.models import PlantLabel

        return PlantLabel.objects.create(uid=uid, user=user, plant=plant)

    def test_unbind_returns_200(self, client):
        """POST unbind-nfc/ returns HTTP 200."""
        user = _make_user("unbind1")
        plant = self._create_plant(user)
        self._bind_label(user, plant, "04B2C3D4E5F6A7")
        extra = _auth_client(client, user)

        response = client.post(
            f"/app/api/plants/{plant.uuid}/unbind-nfc/",
            data=json.dumps({"nfc_id": "04B2C3D4E5F6A7"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 200

    def test_unbind_clears_plant_uuid_to_null(self, client):
        """plant_uuid in response is null after unbinding."""
        user = _make_user("unbind2")
        plant = self._create_plant(user)
        self._bind_label(user, plant, "04C2D3E4F5A6B7")
        extra = _auth_client(client, user)

        response = client.post(
            f"/app/api/plants/{plant.uuid}/unbind-nfc/",
            data=json.dumps({"nfc_id": "04C2D3E4F5A6B7"}),
            content_type="application/json",
            **extra,
        )
        data = response.json()
        assert data["plant_uuid"] is None

    def test_unbind_nfc_id_preserved_in_response(self, client):
        """nfc_id is preserved in the unbind response."""
        user = _make_user("unbind3")
        plant = self._create_plant(user)
        nfc_uid = "04D2E3F4A5B6C7"
        self._bind_label(user, plant, nfc_uid)
        extra = _auth_client(client, user)

        response = client.post(
            f"/app/api/plants/{plant.uuid}/unbind-nfc/",
            data=json.dumps({"nfc_id": nfc_uid}),
            content_type="application/json",
            **extra,
        )
        assert response.json()["nfc_id"] == nfc_uid

    def test_unbind_clears_plant_label_in_db(self, client):
        """PlantLabel.plant FK is null in DB after successful unbind."""
        from domain.models import PlantLabel

        user = _make_user("unbind4")
        plant = self._create_plant(user)
        nfc_uid = "04E2F3A4B5C6D7"
        self._bind_label(user, plant, nfc_uid)
        extra = _auth_client(client, user)

        client.post(
            f"/app/api/plants/{plant.uuid}/unbind-nfc/",
            data=json.dumps({"nfc_id": nfc_uid}),
            content_type="application/json",
            **extra,
        )

        label = PlantLabel.objects.get(uid=nfc_uid, user=user)
        assert label.plant is None

    def test_unbind_no_auth_returns_401(self, client):
        """POST unbind-nfc/ without Authorization returns 401."""
        user = _make_user("unbind5")
        plant = self._create_plant(user)

        response = client.post(
            f"/app/api/plants/{plant.uuid}/unbind-nfc/",
            data=json.dumps({"nfc_id": "04F2A3B4C5D6E7"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_unbind_other_users_plant_returns_404(self, client):
        """User cannot unbind NFC from a plant they do not own — returns 404."""
        owner = _make_user("unbind6a")
        requester = _make_user("unbind6b")
        plant = self._create_plant(owner, "Shared Plant")
        self._bind_label(owner, plant, "04A3B4C5D6E7F8")
        extra = _auth_client(client, requester)

        response = client.post(
            f"/app/api/plants/{plant.uuid}/unbind-nfc/",
            data=json.dumps({"nfc_id": "04A3B4C5D6E7F8"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 404

    def test_unbind_idempotent_for_nonexistent_label(self, client):
        """Unbinding when no label exists is idempotent — returns 200 with null plant_uuid."""
        user = _make_user("unbind7")
        plant = self._create_plant(user)
        nfc_uid = "04B3C4D5E6F7A8"
        extra = _auth_client(client, user)

        # No PlantLabel pre-created — unbind should still succeed idempotently
        response = client.post(
            f"/app/api/plants/{plant.uuid}/unbind-nfc/",
            data=json.dumps({"nfc_id": nfc_uid}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 200
        assert response.json()["plant_uuid"] is None


# ===========================================================================
# User scoping — cannot access other user's data
# ===========================================================================


@pytest.mark.django_db
class TestUserScopingContracts:
    """Verify all plant-mutating endpoints enforce user scoping (own data only)."""

    def _create_plant(self, user, name: str = "Plant"):
        from botany.models import Plant

        return Plant.objects.create(name=name, user=user)

    def test_bind_to_other_users_plant_returns_404(self, client):
        """bind-nfc/ on another user's plant returns 404, not 200 or 403."""
        owner = _make_user("scope_bind_a")
        attacker = _make_user("scope_bind_b")
        plant = self._create_plant(owner)
        extra = _auth_client(client, attacker)

        response = client.post(
            f"/app/api/plants/{plant.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": "04C3D4E5F6A7B8"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 404

    def test_unbind_other_users_plant_returns_404(self, client):
        """unbind-nfc/ on another user's plant returns 404."""
        owner = _make_user("scope_unbind_a")
        attacker = _make_user("scope_unbind_b")
        plant = self._create_plant(owner)
        extra = _auth_client(client, attacker)

        response = client.post(
            f"/app/api/plants/{plant.uuid}/unbind-nfc/",
            data=json.dumps({"nfc_id": "04D3E4F5A6B7C8"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 404

    def test_bind_does_not_create_label_for_wrong_user(self, client):
        """When bind fails with 404, no PlantLabel is created for any user."""
        from domain.models import PlantLabel

        owner = _make_user("scope_leak_a")
        attacker = _make_user("scope_leak_b")
        plant = self._create_plant(owner)
        nfc_uid = "04E3F4A5B6C7D8"
        extra = _auth_client(client, attacker)

        client.post(
            f"/app/api/plants/{plant.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": nfc_uid}),
            content_type="application/json",
            **extra,
        )
        # No label should have been created under any user for this attempted bind
        assert not PlantLabel.objects.filter(uid=nfc_uid).exists()


# ===========================================================================
# Error handling — malformed input
# ===========================================================================


@pytest.mark.django_db
class TestErrorHandlingContracts:
    """Verify endpoints return appropriate status codes for malformed input."""

    def test_bind_nfc_missing_nfc_id_returns_422(self, client):
        """bind-nfc/ without nfc_id in body returns 422."""
        from botany.models import Plant

        user = _make_user("err1")
        plant = Plant.objects.create(name="Test", user=user)
        extra = _auth_client(client, user)

        response = client.post(
            f"/app/api/plants/{plant.uuid}/bind-nfc/",
            data=json.dumps({}),  # Missing nfc_id
            content_type="application/json",
            **extra,
        )
        assert response.status_code == 422

    def test_gbif_search_invalid_limit_returns_422(self, client):
        """limit=0 violates ge=1 constraint and should return 422."""
        response = client.get("/app/api/plants/search-gbif/?q=test&limit=0")
        assert response.status_code == 422

    def test_gbif_search_limit_above_100_returns_422(self, client):
        """limit=101 violates le=100 constraint and should return 422."""
        response = client.get("/app/api/plants/search-gbif/?q=test&limit=101")
        assert response.status_code == 422

    def test_bind_nfc_invalid_plant_uuid_returns_422_or_404(self, client):
        """Malformed UUID in path should return 422; non-existent UUID returns 404."""
        user = _make_user("err2")
        extra = _auth_client(client, user)

        # Completely invalid UUID format — expect 422 (Django-ninja path validation)
        response = client.post(
            "/app/api/plants/not-a-uuid/bind-nfc/",
            data=json.dumps({"nfc_id": "04F3A4B5C6D7E8"}),
            content_type="application/json",
            **extra,
        )
        assert response.status_code in (422, 404)

    def test_create_plant_invalid_json_returns_400_or_422(self, client):
        """Sending malformed JSON to from-gbif/ returns 400 or 422."""
        user = _make_user("err3")
        extra = _auth_client(client, user)
        response = client.post(
            "/app/api/plants/from-gbif/",
            data="not valid json at all",
            content_type="application/json",
            **extra,
        )
        # Django/Ninja typically returns 400 for unparseable JSON bodies
        assert response.status_code in (400, 422)


# ===========================================================================
# NFC uid collision — FIX-3
# ===========================================================================


@pytest.mark.django_db
class TestNFCUidCollisionContract:
    """Verify that uid collisions across users return 409, not 500."""

    def _create_plant(self, user, name: str = "Plant"):
        from botany.models import Plant

        return Plant.objects.create(name=name, user=user)

    def test_bind_nfc_uid_collision_across_users_returns_409(self, client):
        """User A binds uid X; User B tries the same uid X → 409 Conflict (not 500)."""
        user_a = _make_user("coll_a")
        user_b = _make_user("coll_b")
        plant_a = self._create_plant(user_a, "Plant A")
        plant_b = self._create_plant(user_b, "Plant B")
        shared_uid = "04DEADBEEF1122"

        # User A binds the tag successfully
        extra_a = _auth_client(client, user_a)
        resp_a = client.post(
            f"/app/api/plants/{plant_a.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": shared_uid}),
            content_type="application/json",
            **extra_a,
        )
        assert resp_a.status_code == 200, f"User A bind failed: {resp_a.json()}"

        # User B tries the same physical NFC uid → must get 409, not 500
        extra_b = _auth_client(client, user_b)
        resp_b = client.post(
            f"/app/api/plants/{plant_b.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": shared_uid}),
            content_type="application/json",
            **extra_b,
        )
        assert resp_b.status_code == 409, (
            f"Expected 409 for uid collision, got {resp_b.status_code}: {resp_b.json()}"
        )

    def test_bind_nfc_uid_collision_response_has_detail(self, client):
        """409 response contains a 'detail' key with an error message."""
        user_a = _make_user("coll_detail_a")
        user_b = _make_user("coll_detail_b")
        plant_a = self._create_plant(user_a, "Plant A")
        plant_b = self._create_plant(user_b, "Plant B")
        shared_uid = "04DEADBEEF3344"

        extra_a = _auth_client(client, user_a)
        client.post(
            f"/app/api/plants/{plant_a.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": shared_uid}),
            content_type="application/json",
            **extra_a,
        )

        extra_b = _auth_client(client, user_b)
        resp_b = client.post(
            f"/app/api/plants/{plant_b.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": shared_uid}),
            content_type="application/json",
            **extra_b,
        )
        assert resp_b.status_code == 409
        data = resp_b.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)
        assert len(data["detail"]) > 0

    def test_bind_nfc_same_user_rebind_still_works(self, client):
        """Same user rebinding the same uid to a different plant is still 200."""
        user = _make_user("coll_rebind")
        plant1 = self._create_plant(user, "Plant 1")
        plant2 = self._create_plant(user, "Plant 2")
        uid = "04DEADBEEF5566"

        extra = _auth_client(client, user)
        # First bind
        r1 = client.post(
            f"/app/api/plants/{plant1.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": uid}),
            content_type="application/json",
            **extra,
        )
        assert r1.status_code == 200

        # Rebind to another plant — same user, same uid — should be 200
        r2 = client.post(
            f"/app/api/plants/{plant2.uuid}/bind-nfc/",
            data=json.dumps({"nfc_id": uid}),
            content_type="application/json",
            **extra,
        )
        assert r2.status_code == 200
        assert r2.json()["plant_uuid"] == str(plant2.uuid)


# ===========================================================================
# GET /app/api/plants/  — list user's plants (paginated)
# ===========================================================================


@pytest.mark.django_db
class TestListPlantsContract:
    """Verify GET /app/api/plants/ response schema, pagination, and user scoping."""

    def _create_plant(self, user, name: str = "Monstera"):
        from botany.models import Plant

        return Plant.objects.create(name=name, user=user)

    def test_list_plants_paginated(self, client):
        """GET /app/api/plants/ returns count, limit, offset, and results."""
        user = _make_user("list1")
        self._create_plant(user, "Plant A")
        self._create_plant(user, "Plant B")
        extra = _auth_client(client, user)

        response = client.get("/app/api/plants/?limit=20&offset=0", **extra)

        assert response.status_code == 200
        data = response.json()
        for field in ("count", "limit", "offset", "results"):
            assert field in data, f"Response missing required field: {field}"
        assert isinstance(data["count"], int)
        assert isinstance(data["limit"], int)
        assert isinstance(data["offset"], int)
        assert isinstance(data["results"], list)
        assert data["count"] == 2
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_list_plants_user_scoped(self, client):
        """User A's plants are not visible to User B."""
        user_a = _make_user("list_scope_a")
        user_b = _make_user("list_scope_b")
        self._create_plant(user_a, "User A's Plant")
        extra_b = _auth_client(client, user_b)

        response = client.get("/app/api/plants/?limit=20&offset=0", **extra_b)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_list_plants_empty_list_ok(self, client):
        """User with no plants gets an empty results list with count=0."""
        user = _make_user("list_empty")
        extra = _auth_client(client, user)

        response = client.get("/app/api/plants/?limit=20&offset=0", **extra)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_list_plants_no_auth_returns_401(self, client):
        """GET /app/api/plants/ without auth returns 401."""
        response = client.get("/app/api/plants/?limit=20&offset=0")
        assert response.status_code == 401

    def test_list_plants_result_has_bound_field(self, client):
        """Each result in results[] contains a 'bound' boolean field."""
        from botany.models import Plant
        from domain.models import PlantLabel

        user = _make_user("list_bound")
        plant_bound = Plant.objects.create(name="Bound Plant", user=user)
        plant_unbound = Plant.objects.create(name="Unbound Plant", user=user)
        PlantLabel.objects.create(uid="04AABBCCDD1122", user=user, plant=plant_bound)
        extra = _auth_client(client, user)

        response = client.get("/app/api/plants/?limit=20&offset=0", **extra)

        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) == 2
        result_by_uuid = {r["uuid"]: r for r in results}
        assert result_by_uuid[str(plant_bound.uuid)]["bound"] is True
        assert result_by_uuid[str(plant_unbound.uuid)]["bound"] is False

    def test_list_plants_pagination_offset(self, client):
        """offset param is honoured — skips the first N results."""
        user = _make_user("list_offset")
        for i in range(5):
            self._create_plant(user, f"Plant {i}")
        extra = _auth_client(client, user)

        response = client.get("/app/api/plants/?limit=3&offset=3", **extra)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 5
        assert len(data["results"]) == 2
        assert data["offset"] == 3
        assert data["limit"] == 3


# ===========================================================================
# GET /app/api/plants/search-gbif/species/{usage_key}/
# ===========================================================================


_MOCK_GBIF_DETAIL = {
    "key": 2884241,
    "nubKey": 2884241,
    "scientificName": "Monstera deliciosa Liebm.",
    "canonicalName": "Monstera deliciosa",
    "rank": "SPECIES",
    "kingdom": "Plantae",
    "phylum": "Tracheophyta",
    "class": "Liliopsida",
    "order": "Alismatales",
    "family": "Araceae",
    "genus": "Monstera",
    "taxonomicStatus": "ACCEPTED",
}


@pytest.mark.django_db
class TestGBIFSpeciesDetailContract:
    """Verify GET /app/api/plants/search-gbif/species/{usage_key}/ response."""

    def test_get_gbif_species_by_usage_key_returns_200(self, client):
        """GET /app/api/plants/search-gbif/species/2884241/ returns 200."""
        with patch("botany.services.species") as mock_species:
            mock_species.name_usage.return_value = _MOCK_GBIF_DETAIL
            response = client.get("/app/api/plants/search-gbif/species/2884241/")
        assert response.status_code == 200

    def test_get_gbif_species_response_has_key_field(self, client):
        """Response from GBIF detail endpoint contains a 'key' field (usage key)."""
        with patch("botany.services.species") as mock_species:
            mock_species.name_usage.return_value = _MOCK_GBIF_DETAIL
            response = client.get("/app/api/plants/search-gbif/species/2884241/")
        data = response.json()
        assert "key" in data
        assert data["key"] == 2884241

    def test_get_gbif_species_not_found_returns_404(self, client):
        """GET with a usage_key that resolves to nothing returns 404."""
        with patch("botany.services.species") as mock_species:
            mock_species.name_usage.return_value = {}
            response = client.get("/app/api/plants/search-gbif/species/9999999999/")
        assert response.status_code == 404

    def test_get_gbif_species_endpoint_is_public(self, client):
        """No Authorization header needed — endpoint returns 200 without auth."""
        with patch("botany.services.species") as mock_species:
            mock_species.name_usage.return_value = _MOCK_GBIF_DETAIL
            response = client.get("/app/api/plants/search-gbif/species/2884241/")
        assert response.status_code == 200
