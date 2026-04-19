"""
Tests for the /app/api/plants/search-gbif/ and /app/api/plants/from-gbif/ endpoints.

Verifies:
- Basic search returns paginated GBIF results
- Family filter is forwarded
- Pagination parameters (limit, offset) are respected
- Missing required q param returns 422
- Plant creation from GBIF requires auth and returns 201 with plant data
"""

import json
import time
from pathlib import Path
from unittest.mock import patch

import jwt
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------


def _create_test_jwt_token(user):
    """
    Create a RS256 JWT token for the given user using the ID service private key.

    Skips the test automatically if the key file is not found (CI/environments
    without the ID service repo checked out).
    """
    private_key_path = (
        Path(__file__).resolve().parent.parent.parent.parent
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
    """Return 'Bearer <token>' authorization header value for the given user."""
    return f"Bearer {_create_test_jwt_token(user)}"


def _make_user(suffix: str):
    """Create and return a unique User for tests."""
    return User.objects.create_user(
        username=f"plant_api_user_{suffix}",
        email=f"plant_api_{suffix}@example.com",
        password="testpass",
    )


MOCK_GBIF_SEARCH_RESPONSE = {
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
                {"vernacularName": "tomate", "language": "spa"},
            ],
        },
    ],
}


@pytest.mark.django_db
class TestGBIFSearchAPI:
    def test_search_gbif_endpoint_returns_results(self, client):
        """GET /app/api/plants/search-gbif/ returns paginated GBIF results."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = MOCK_GBIF_SEARCH_RESPONSE

            response = client.get(
                "/app/api/plants/search-gbif/?q=tomato&limit=20&offset=0"
            )

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "limit" in data
        assert "offset" in data
        assert "results" in data
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_search_gbif_with_family_filter(self, client):
        """GET /app/api/plants/search-gbif/?q=solanum&family=Solanaceae returns filtered results."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = MOCK_GBIF_SEARCH_RESPONSE

            response = client.get(
                "/app/api/plants/search-gbif/?q=solanum&family=Solanaceae"
            )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        # Verify family filter was forwarded to pygbif
        mock_species.search.assert_called_once()
        call_kwargs = mock_species.search.call_args.kwargs
        assert call_kwargs.get("family") == "Solanaceae"
        for result in data.get("results", []):
            assert "scientificName" in result

    def test_search_gbif_missing_q_param(self, client):
        """GET /app/api/plants/search-gbif/ without q param returns 422 Unprocessable Entity."""
        response = client.get("/app/api/plants/search-gbif/")
        assert response.status_code == 422

    def test_search_gbif_pagination(self, client):
        """GET /app/api/plants/search-gbif/?q=...&limit=10&offset=10 respects pagination."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = {
                **MOCK_GBIF_SEARCH_RESPONSE,
                "limit": 10,
                "offset": 10,
            }

            response = client.get(
                "/app/api/plants/search-gbif/?q=plant&limit=10&offset=10"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 10


# ---------------------------------------------------------------------------
# POST /app/api/plants/from-gbif/ — Create Plant from GBIF
# ---------------------------------------------------------------------------

MOCK_GBIF_DETAILS_TOMATO = {
    "key": 5289683,
    "usageKey": 5289683,
    "scientificName": "Solanum lycopersicum L.",
    "canonicalName": "Solanum lycopersicum",
    "rank": "SPECIES",
    "kingdom": "Plantae",
    "family": "Solanaceae",
}


@pytest.mark.django_db
class TestCreatePlantFromGBIF:
    """Tests for POST /app/api/plants/from-gbif/

    The endpoint accepts gbif_id + name (required) plus optional metadata,
    creates a Plant scoped to the authenticated user, and returns 201.
    """

    def test_create_plant_from_gbif_requires_auth(self, client):
        """POST /app/api/plants/from-gbif/ without auth returns 401."""
        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"gbif_id": 5289683, "name": "Tomato"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_plant_from_gbif_success(self, client):
        """POST /app/api/plants/from-gbif/ with auth creates a Plant scoped to the user."""
        user = _make_user("success1")
        client.login(username=user.username, password="testpass")

        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps(
                {
                    "gbif_id": 5289683,
                    "name": "Solanum lycopersicum",
                    "acquisition_date": "2026-04-18",
                    "location": "Nursery",
                    "notes": "From seed",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=_auth_header(user),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["gbif_id"] == 5289683
        assert data["name"] == "Solanum lycopersicum"
        assert data["location"] == "Nursery"
        assert data["notes"] == "From seed"
        assert data["acquisition_date"] == "2026-04-18"

        # Verify plant is scoped to the authenticated user
        from botany.models import Plant

        plant = Plant.objects.get(gbif_id=5289683, user=user)
        assert plant.name == "Solanum lycopersicum"

    def test_create_plant_missing_required_fields(self, client):
        """POST /app/api/plants/from-gbif/ without gbif_id returns 422."""
        user = _make_user("missing1")
        client.login(username=user.username, password="testpass")

        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps({"name": "Tomato"}),  # Missing gbif_id
            content_type="application/json",
            HTTP_AUTHORIZATION=_auth_header(user),
        )
        assert response.status_code == 422

    def test_create_plant_optional_metadata(self, client):
        """POST /app/api/plants/from-gbif/ succeeds without optional metadata fields."""
        user = _make_user("optional1")
        client.login(username=user.username, password="testpass")

        response = client.post(
            "/app/api/plants/from-gbif/",
            data=json.dumps(
                {
                    "gbif_id": 5289683,
                    "name": "Solanum lycopersicum",
                    # Omit all optional fields
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=_auth_header(user),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["gbif_id"] == 5289683
        assert data["name"] == "Solanum lycopersicum"
        assert data["location"] is None or data["location"] == ""
        assert data["notes"] is None or data["notes"] == ""
