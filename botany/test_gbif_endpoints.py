"""
Tests for the GBIF search endpoint.

Verifies:
- Basic search returns paginated results
- Family filter is forwarded to pygbif
- Results are cached and pygbif is only called once per unique query
"""

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


MOCK_GBIF_SEARCH_RESPONSE = {
    "offset": 0,
    "limit": 20,
    "endOfRecords": False,
    "count": 42,
    "results": [
        {
            "usageKey": 2684241,
            "scientificName": "Monstera deliciosa Liebm.",
            "canonicalName": "Monstera deliciosa",
            "rank": "SPECIES",
            "kingdom": "Plantae",
            "phylum": "Tracheophyta",
            "class": "Liliopsida",
            "order": "Alismatales",
            "family": "Araceae",
            "genus": "Monstera",
            "vernacularNames": [
                {"vernacularName": "Swiss Cheese Plant", "language": "eng"}
            ],
        },
        {
            "usageKey": 7698902,
            "scientificName": "Monstera adansonii Schott",
            "canonicalName": "Monstera adansonii",
            "rank": "SPECIES",
            "kingdom": "Plantae",
            "phylum": "Tracheophyta",
            "class": "Liliopsida",
            "order": "Alismatales",
            "family": "Araceae",
            "genus": "Monstera",
            "vernacularNames": [],
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGBIFSearchEndpoint:
    """Tests for GET /app/api/gbif/search/"""

    @pytest.mark.django_db
    def test_gbif_search_success(self, client):
        """Basic search returns paginated results with correct structure."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = MOCK_GBIF_SEARCH_RESPONSE

            response = client.get("/app/api/gbif/search/?q=monstera")

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 42
        assert data["limit"] == 20
        assert data["offset"] == 0
        assert len(data["results"]) == 2

        first = data["results"][0]
        assert first["usageKey"] == 2684241
        assert first["scientificName"] == "Monstera deliciosa Liebm."
        assert first["canonicalName"] == "Monstera deliciosa"
        assert first["rank"] == "SPECIES"
        assert first["kingdom"] == "Plantae"
        assert first["family"] == "Araceae"
        assert "Swiss Cheese Plant" in first["commonNames"]

    @pytest.mark.django_db
    def test_gbif_search_requires_query_param(self, client):
        """Search endpoint returns 422 when q parameter is missing."""
        response = client.get("/app/api/gbif/search/")
        assert response.status_code == 422

    @pytest.mark.django_db
    def test_gbif_search_with_family_filter(self, client):
        """Family filter is forwarded to pygbif species.search."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = MOCK_GBIF_SEARCH_RESPONSE

            response = client.get("/app/api/gbif/search/?q=monstera&family=Araceae")

        assert response.status_code == 200

        # Verify family was passed to pygbif
        mock_species.search.assert_called_once()
        call_kwargs = mock_species.search.call_args.kwargs
        assert call_kwargs.get("family") == "Araceae"

    @pytest.mark.django_db
    def test_gbif_search_without_family_filter(self, client):
        """Search without family filter calls pygbif without family kwarg."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = {
                **MOCK_GBIF_SEARCH_RESPONSE,
                "count": 100,
            }

            response = client.get("/app/api/gbif/search/?q=ficus")

        assert response.status_code == 200
        call_kwargs = mock_species.search.call_args.kwargs
        # family should not be present when not specified
        assert "family" not in call_kwargs or call_kwargs["family"] is None

    @pytest.mark.django_db
    def test_gbif_search_caching(self, client):
        """pygbif search is called once; subsequent identical requests use cache."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = MOCK_GBIF_SEARCH_RESPONSE

            # Use a unique query to avoid collisions with other tests
            response1 = client.get("/app/api/gbif/search/?q=cachetest_unique_xyz")
            response2 = client.get("/app/api/gbif/search/?q=cachetest_unique_xyz")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # pygbif should only have been called once; the second hit is from cache
        assert mock_species.search.call_count == 1

    @pytest.mark.django_db
    def test_gbif_search_no_authentication_required(self, client):
        """Search endpoint is public — no authentication needed."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = {
                **MOCK_GBIF_SEARCH_RESPONSE,
                "count": 0,
                "results": [],
            }

            # No Authorization header, no session — should still get 200
            response = client.get("/app/api/gbif/search/?q=public")

        assert response.status_code == 200

    @pytest.mark.django_db
    def test_gbif_search_error_returns_500(self, client):
        """When pygbif raises an exception, the endpoint returns HTTP 500."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.side_effect = Exception("GBIF is down")

            response = client.get("/app/api/gbif/search/?q=broken")

        assert response.status_code == 500

    @pytest.mark.django_db
    def test_gbif_search_limit_and_offset_forwarded(self, client):
        """limit and offset query params are forwarded to pygbif."""
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = {
                **MOCK_GBIF_SEARCH_RESPONSE,
                "offset": 20,
                "limit": 10,
            }

            response = client.get("/app/api/gbif/search/?q=fern&limit=10&offset=20")

        assert response.status_code == 200
        call_kwargs = mock_species.search.call_args.kwargs
        assert call_kwargs.get("limit") == 10
        assert call_kwargs.get("offset") == 20

    @pytest.mark.django_db
    def test_gbif_search_result_with_no_common_names(self, client):
        """Results with no vernacularNames produce an empty commonNames list."""
        response_with_empty_names = {
            "offset": 0,
            "limit": 20,
            "count": 1,
            "results": [
                {
                    "usageKey": 9999,
                    "scientificName": "Unknown species",
                    "canonicalName": "Unknown species",
                    "rank": "SPECIES",
                    "vernacularNames": [],
                }
            ],
        }
        with patch("botany.services.species") as mock_species:
            mock_species.search.return_value = response_with_empty_names

            response = client.get("/app/api/gbif/search/?q=unknown")

        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["commonNames"] == []
