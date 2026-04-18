import time
import uuid as uuid_module
from typing import TYPE_CHECKING

import jwt
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

if TYPE_CHECKING:
    import django.test

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


def _make_user(suffix: str) -> "User":
    """Create a unique user for tests."""
    return User.objects.create_user(
        username=f"user_{suffix}",
        email=f"user_{suffix}@example.com",
        password="testpass",
    )


def _make_plant(user: "User", name: str = "Test Plant") -> Plant:
    """Create a Plant owned by the given user."""
    return Plant.objects.create(
        name=name,
        user=user,
    )


def _make_plant_label(user: "User", plant: Plant | None = None) -> PlantLabel:
    """Create a PlantLabel (NFC tag) owned by the given user."""
    label = PlantLabel.objects.create(
        uid=f"UID{uuid_module.uuid4().hex[:8].upper()}",
        user=user,
        plant=plant,
    )
    return label


def _auth_header(user: "User") -> str:
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

        client.login(username=user.username, password="testpass")
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

        client.login(username=user1.username, password="testpass")
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

        client.login(username=user1.username, password="testpass")
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

        client.login(username=user.username, password="testpass")
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

        client.login(username=user.username, password="testpass")
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

        client.login(username=user.username, password="testpass")
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

        client.login(username=user.username, password="testpass")
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
