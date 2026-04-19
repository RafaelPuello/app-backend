"""
Tests for the /app/api/plants/search-gbif/ endpoint.

Verifies:
- Basic search returns paginated GBIF results
- Family filter is forwarded
- Pagination parameters (limit, offset) are respected
- Missing required q param returns 422
"""

from unittest.mock import patch

import pytest


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
