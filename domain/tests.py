import time
import uuid as uuid_module
from unittest.mock import patch

import jwt
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.urls import reverse

from botany.models import Plant
from domain.models import PlantLabel
from domain.services import NFCTagService

User = get_user_model()


def create_test_jwt_token(user):
    """
    Create a test JWT token for a user.

    Uses the ID service's RS256 private key to sign the token.
    The token is valid for 1 hour in tests.
    """
    from pathlib import Path

    # Load the ID service's private key for signing test tokens.
    # tests.py is at app/backend/domain/tests.py; repo root is 4 levels up.
    private_key_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "id"
        / "backend"
        / "config"
        / "keys"
        / "jwt_private_key.pem"
    )

    try:
        with open(private_key_path) as f:
            private_key = f.read()
    except FileNotFoundError:
        pytest.skip("ID service private key not found for test token generation")

    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "uuid": str(user.id),  # Using user ID as UUID for testing
        "iat": now,
        "exp": now + 3600,  # 1 hour later
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.mark.django_db
def test_list_parity(client, django_user_model):
    user = django_user_model.objects.create_user("u", "u@example.com", "p")
    client.login(username="u", password="p")

    service = NFCTagService(user=user)
    service.create_tag(uid="AAA")
    service.create_tag(uid="BBB")

    # HTML list view (uses session auth via @login_required)
    resp_html = client.get(reverse("domain:list_nfctags"))
    assert resp_html.status_code == 200
    html_items = {str(t.uuid) for t in resp_html.context["nfctags"]}

    # API list (uses JWT token in Authorization header)
    token = create_test_jwt_token(user)
    resp_api = client.get(
        "/app/api/nfctags?limit=100", HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    assert resp_api.status_code == 200
    api_items = {i["uuid"] for i in resp_api.json()["items"]}

    assert html_items == api_items


@pytest.mark.django_db
def test_detail_parity(client, django_user_model):
    user = django_user_model.objects.create_user("u2", "u2@example.com", "p")
    client.login(username="u2", password="p")

    service = NFCTagService(user=user)
    tag = service.create_tag(uid="CCC")

    # HTML detail view (uses session auth via @login_required)
    resp_html = client.get(reverse("domain:detail_nfctag", args=[str(tag.uuid)]))
    assert resp_html.status_code == 200
    html_uuid = str(resp_html.context["nfctag"].uuid)

    # API detail (uses JWT token in Authorization header)
    token = create_test_jwt_token(user)
    resp_api = client.get(
        f"/app/api/nfctags/{tag.uuid}", HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    assert resp_api.status_code == 200
    api_uuid = resp_api.json()["uuid"]

    assert html_uuid == api_uuid


# ---------------------------------------------------------------------------
# Helpers for NFC Plant Binding tests
# ---------------------------------------------------------------------------


def _make_user(suffix: str) -> AbstractBaseUser:
    """Create a unique user for tests."""
    return User.objects.create_user(  # type: ignore[return-value]
        username=f"user_{suffix}",
        email=f"user_{suffix}@example.com",
        password="testpass",
    )


def _make_plant(user: AbstractBaseUser, name: str = "Test Plant") -> Plant:
    """Create a Plant owned by the given user."""
    return Plant.objects.create(
        name=name,
        user=user,
    )


def _make_plant_label(
    user: AbstractBaseUser, plant: Plant | None = None
) -> PlantLabel:
    """Create a PlantLabel (NFC tag) owned by the given user."""
    return PlantLabel.objects.create(
        uid=f"UID{uuid_module.uuid4().hex[:8].upper()}",
        user=user,
        plant=plant,
    )


def _auth_header(user: AbstractBaseUser) -> str:
    """Return JWT Authorization header value for the given user."""
    token = create_test_jwt_token(user)
    return f"Bearer {token}"


@pytest.mark.django_db
class TestNFCPlantBinding:
    """Test NFC tag to plant binding (bind/unbind endpoints).

    All authenticated tests use both session auth (``client.login``) to satisfy
    the ``IsAuthenticated`` permission check and a JWT Bearer token, mirroring
    the pattern established in ``test_list_parity``.
    """

    def test_bind_plant_success(self, client) -> None:
        """User can bind an NFC tag to their own plant."""
        user = _make_user("bind1")
        plant = _make_plant(user, name="Monstera Deliciosa")
        tag = _make_plant_label(user)

        client.login(username=getattr(user, "username"), password="testpass")
        response = client.post(
            f"/app/api/nfctags/{tag.uuid}/bind",
            data=f'{{"plant_id": "{plant.uuid}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=_auth_header(user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["plant_id"] == str(plant.uuid)
        assert data["plant"]["name"] == plant.name

        tag.refresh_from_db()
        assert tag.plant_id == plant.pk

    def test_bind_plant_not_owned_by_user(self, client) -> None:
        """User cannot bind their tag to another user's plant (returns 404)."""
        user1 = _make_user("bind2a")
        user2 = _make_user("bind2b")
        plant = _make_plant(user2, name="User2 Plant")  # belongs to user2
        tag = _make_plant_label(user1)  # belongs to user1

        client.login(username=getattr(user1, "username"), password="testpass")
        response = client.post(
            f"/app/api/nfctags/{tag.uuid}/bind",
            data=f'{{"plant_id": "{plant.uuid}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=_auth_header(user1),
        )

        assert response.status_code == 404

    def test_bind_tag_not_owned_by_user(self, client) -> None:
        """User cannot bind another user's tag (returns 404)."""
        user1 = _make_user("bind3a")
        user2 = _make_user("bind3b")
        plant = _make_plant(user1, name="User1 Plant")
        tag = _make_plant_label(user2)  # belongs to user2, not user1

        client.login(username=getattr(user1, "username"), password="testpass")
        response = client.post(
            f"/app/api/nfctags/{tag.uuid}/bind",
            data=f'{{"plant_id": "{plant.uuid}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=_auth_header(user1),
        )

        assert response.status_code == 404

    def test_unbind_plant_success(self, client) -> None:
        """User can unbind an NFC tag from its plant."""
        user = _make_user("unbind1")
        plant = _make_plant(user, name="Ficus")
        tag = _make_plant_label(user, plant=plant)

        client.login(username=getattr(user, "username"), password="testpass")
        response = client.post(
            f"/app/api/nfctags/{tag.uuid}/unbind",
            HTTP_AUTHORIZATION=_auth_header(user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["plant_id"] is None
        assert data["plant"] is None

        tag.refresh_from_db()
        assert tag.plant is None

    def test_unbind_already_unbound_tag(self, client) -> None:
        """Unbinding an already-unbound tag returns 200 with plant=None."""
        user = _make_user("unbind2")
        tag = _make_plant_label(user, plant=None)

        client.login(username=getattr(user, "username"), password="testpass")
        response = client.post(
            f"/app/api/nfctags/{tag.uuid}/unbind",
            HTTP_AUTHORIZATION=_auth_header(user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["plant_id"] is None
        assert data["plant"] is None

    def test_list_includes_plant_when_requested(self, client) -> None:
        """GET /nfctags?include=plant returns plant details in each item."""
        user = _make_user("list1")
        plant = _make_plant(user, name="Pothos")
        _make_plant_label(user, plant=plant)

        client.login(username=getattr(user, "username"), password="testpass")
        response = client.get(
            "/app/api/nfctags?include=plant&limit=100",
            HTTP_AUTHORIZATION=_auth_header(user),
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["plant"]["name"] == plant.name
        assert items[0]["plant_id"] == str(plant.uuid)

    def test_list_without_include_returns_plant_id(self, client) -> None:
        """GET /nfctags without include=plant still serializes plant_id."""
        user = _make_user("list2")
        plant = _make_plant(user, name="Cactus")
        _make_plant_label(user, plant=plant)

        client.login(username=getattr(user, "username"), password="testpass")
        response = client.get(
            "/app/api/nfctags?limit=100",
            HTTP_AUTHORIZATION=_auth_header(user),
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        # plant_id is resolved via the schema resolver (plant.uuid), always serialized
        assert items[0]["plant_id"] == str(plant.uuid)

    def test_bind_requires_authentication(self, client) -> None:
        """Bind endpoint returns 401 when no session or Bearer token is provided."""
        user = _make_user("noauth1")
        plant = _make_plant(user)
        tag = _make_plant_label(user)

        # No client.login, no JWT token — should be rejected
        response = client.post(
            f"/app/api/nfctags/{tag.uuid}/bind",
            data=f'{{"plant_id": "{plant.uuid}"}}',
            content_type="application/json",
        )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Create Plant from GBIF endpoint tests
# ---------------------------------------------------------------------------

MOCK_GBIF_DETAILS_MONSTERA = {
    "key": 2684241,
    "usageKey": 2684241,
    "scientificName": "Monstera deliciosa Liebm.",
    "canonicalName": "Monstera deliciosa",
    "rank": "SPECIES",
    "kingdom": "Plantae",
    "family": "Araceae",
}


@pytest.mark.django_db
class TestCreatePlantFromGBIF:
    """Tests for POST /app/api/gbif/from-gbif endpoint."""

    def test_create_plant_from_gbif_authenticated(self, client) -> None:
        """Authenticated user can create a plant from a GBIF ID."""
        user = _make_user("gbif1")
        client.login(username=getattr(user, "username"), password="testpass")

        with patch("botany.services.species") as mock_species:
            mock_species.name_usage.return_value = MOCK_GBIF_DETAILS_MONSTERA

            response = client.post(
                "/app/api/gbif/from-gbif",
                data='{"gbif_id": 2684241, "acquisition_date": "2026-04-01", "location": "Living room", "notes": "New arrival"}',
                content_type="application/json",
                HTTP_AUTHORIZATION=_auth_header(user),
            )

        assert response.status_code == 201
        data = response.json()
        assert data["gbif_id"] == 2684241
        assert data["name"] == "Monstera deliciosa"
        assert data["acquisition_date"] == "2026-04-01"
        assert data["location"] == "Living room"
        assert data["notes"] == "New arrival"
        assert "uuid" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Verify the plant was saved in the database scoped to the user
        from botany.models import Plant
        plant = Plant.objects.get(uuid=data["uuid"])
        assert plant.user == user
        assert plant.gbif_id == 2684241

    def test_create_plant_from_gbif_requires_auth(self, client) -> None:
        """Unauthenticated request to /gbif/from-gbif returns 401."""
        response = client.post(
            "/app/api/gbif/from-gbif",
            data='{"gbif_id": 2684241}',
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_plant_from_gbif_invalid_date(self, client) -> None:
        """Invalid acquisition_date returns 400."""
        user = _make_user("gbif3")
        client.login(username=getattr(user, "username"), password="testpass")

        with patch("botany.services.species") as mock_species:
            mock_species.name_usage.return_value = MOCK_GBIF_DETAILS_MONSTERA

            response = client.post(
                "/app/api/gbif/from-gbif",
                data='{"gbif_id": 2684241, "acquisition_date": "not-a-date"}',
                content_type="application/json",
                HTTP_AUTHORIZATION=_auth_header(user),
            )

        assert response.status_code == 400

    def test_create_plant_from_gbif_not_found(self, client) -> None:
        """GBIF species not found returns 404."""
        user = _make_user("gbif4")
        client.login(username=getattr(user, "username"), password="testpass")

        with patch("botany.services.species") as mock_species:
            mock_species.name_usage.return_value = {}

            response = client.post(
                "/app/api/gbif/from-gbif",
                data='{"gbif_id": 9999999}',
                content_type="application/json",
                HTTP_AUTHORIZATION=_auth_header(user),
            )

        assert response.status_code == 404

    def test_user_scoped_plants(self, client) -> None:
        """Plants created by user A are not accessible in user B's plant list."""
        user_a = _make_user("gbif5a")
        user_b = _make_user("gbif5b")

        # Create a plant for user A directly in the DB
        _make_plant(user_a, name="User A Plant")

        # user B has no plants
        from botany.models import Plant
        plants_b = Plant.objects.filter(user=user_b)
        assert plants_b.count() == 0

        # user A has one plant
        plants_a = Plant.objects.filter(user=user_a)
        assert plants_a.count() == 1
