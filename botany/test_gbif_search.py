"""
Tests for the search_gbif_species service function.

Verifies:
- Returns paginated results from GBIF
- Supports optional family filter
- Caches results for 1 hour (pygbif called only once per unique query)
- Propagates errors from pygbif
"""

import pytest
from unittest.mock import patch
from botany.services import search_gbif_species


@pytest.mark.django_db
class TestGBIFSearch:
    @patch("botany.services.species")
    def test_search_gbif_returns_results(self, mock_species):
        """GBIF search returns paginated results."""
        mock_species.search.return_value = {
            "count": 432,
            "limit": 20,
            "offset": 0,
            "results": [
                {
                    "usageKey": 5289683,
                    "scientificName": "Solanum lycopersicum",
                    "canonicalName": "Solanum lycopersicum",
                    "rank": "SPECIES",
                    "kingdom": "Plantae",
                    "phylum": "Tracheophyta",
                    "class": "Dicotyledonopsida",
                    "order": "Solanales",
                    "family": "Solanaceae",
                    "genus": "Solanum",
                    "vernacularNames": [
                        {"vernacularName": "tomato"},
                        {"vernacularName": "tomate"},
                    ],
                }
            ],
        }
        result = search_gbif_species(q="tomato", limit=20, offset=0)
        assert result["count"] == 432
        assert len(result["results"]) == 1
        assert result["results"][0]["usageKey"] == 5289683

    @patch("botany.services.species")
    def test_search_gbif_with_family_filter(self, mock_species):
        """GBIF search supports optional family filter."""
        mock_species.search.return_value = {
            "count": 120,
            "limit": 20,
            "offset": 0,
            "results": [
                {
                    "usageKey": 5289683,
                    "family": "Solanaceae",
                    "scientificName": "Solanum lycopersicum",
                    "vernacularNames": [],
                }
            ],
        }
        result = search_gbif_species(q="solanum", family="Solanaceae", limit=20, offset=0)
        assert result["count"] == 120
        # Verify family filter was passed to pygbif
        mock_species.search.assert_called_once()
        call_kwargs = mock_species.search.call_args.kwargs
        assert call_kwargs.get("family") == "Solanaceae"

    @patch("botany.services.species")
    def test_search_gbif_caching(self, mock_species):
        """GBIF search results are cached for 1 hour."""
        mock_species.search.return_value = {
            "count": 432,
            "limit": 20,
            "offset": 0,
            "results": [
                {
                    "usageKey": 5289683,
                    "scientificName": "Solanum lycopersicum",
                    "vernacularNames": [],
                }
            ],
        }
        # First call
        result1 = search_gbif_species(q="tomato_service_cache_test", limit=20, offset=0)
        # Second call with same params
        result2 = search_gbif_species(q="tomato_service_cache_test", limit=20, offset=0)

        # GBIF API should only be called once (second call hits cache)
        assert mock_species.search.call_count == 1
        assert result1 == result2

    @patch("botany.services.species")
    def test_search_gbif_error_handling(self, mock_species):
        """GBIF search propagates API errors to the caller."""
        mock_species.search.side_effect = Exception("GBIF API Error")
        with pytest.raises(Exception):
            # Use a unique query so no cached result masks the error
            search_gbif_species(q="tomato_error_unique_xyz", limit=20, offset=0)
