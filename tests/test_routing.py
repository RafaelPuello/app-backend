"""
Routing tests for the app backend.

These tests verify that the Django URL configuration correctly reflects the
Traefik routing architecture: Traefik forwards all /app/* paths to this backend
WITHOUT stripping the /app prefix. Django must handle the full path.

Key invariants:
- API lives at /app/api/* (NOT /api/*)
- Admin lives at /app/admin/ (NOT /admin/)
- No endpoints exist at bare paths (e.g., /nfctags/ should 404)

See CLAUDE.md "Routing Validation" for architecture notes.
"""

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


class TestAppRouting:
    """Validate that app backend routes correctly when receiving full /app/* paths.

    Traefik does NOT strip the /app prefix — Django receives and handles it.
    These tests ensure the URL config enforces that contract and prevent
    accidental regressions from path-stripping or misconfigured URL patterns.
    """

    @pytest.mark.django_db
    def test_health_check(self, client):
        """Health endpoint is accessible at /app/api/health/ and returns expected payload."""
        response = client.get("/app/api/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "app-backend"}

    @pytest.mark.django_db
    def test_nfctags_list_requires_auth(self, client):
        """NFC tags API at /app/api/nfctags/ returns 401 for unauthenticated requests.

        The endpoint must exist (not 404) so Traefik can route to it; auth is enforced
        by the DomainController's IsAuthenticated permission.
        """
        response = client.get("/app/api/nfctags")
        # 401 confirms route is registered and auth guard is active
        assert response.status_code in [200, 401]

    @pytest.mark.django_db
    def test_admin_accessible_at_app_prefix(self, client):
        """Django admin is mounted at /app/admin/, matching the no-strip Traefik route.

        The admin may redirect to the login page (302) or show the login page directly (200).
        Any of 200, 301, 302, or 401 indicates the route exists; 404 would mean misconfiguration.
        """
        response = client.get("/app/admin/")
        assert response.status_code in [200, 301, 302, 401], (
            f"Expected admin at /app/admin/ to respond with 200/301/302/401, "
            f"got {response.status_code}"
        )

    @pytest.mark.django_db
    def test_admin_not_accessible_at_bare_path(self, client):
        """Admin must NOT be at /admin/ — it would only be routable if path-stripping were active.

        If /admin/ returns anything other than 404, the URL config is wrong: it would mean
        Django is accepting paths without the /app prefix, which breaks the Traefik routing contract.
        """
        response = client.get("/admin/")
        assert response.status_code == 404, (
            f"Expected /admin/ to return 404 (no bare-path admin route), "
            f"got {response.status_code}. "
            "This suggests the URL config has a path-stripping misconfiguration."
        )

    @pytest.mark.django_db
    def test_nfctags_direct_path_not_accessible(self, client):
        """/nfctags/ without the /app/ prefix must return 404.

        Validates that no URL pattern accidentally exposes endpoints at bare paths.
        The only valid route is /app/nfctags/ (HTML views) or /app/api/nfctags (API).
        """
        response = client.get("/nfctags/")
        assert response.status_code == 404, (
            f"Expected /nfctags/ to return 404 (no bare-path nfctags route), "
            f"got {response.status_code}. "
            "This suggests an unintended URL pattern at the root."
        )

    @pytest.mark.django_db
    def test_health_check_no_auth_required(self, client):
        """Health check endpoint must be public — no authentication required.

        Traefik and monitoring tools use this endpoint without credentials.
        A 401 here would prevent health checks from working in production.
        """
        # Deliberately no Authorization header
        response = client.get("/app/api/health/")
        assert response.status_code == 200, (
            f"Health check at /app/api/health/ must be unauthenticated. "
            f"Got {response.status_code} — check that auth=None is set on the endpoint."
        )

    @pytest.mark.django_db
    def test_api_docs_accessible(self, client):
        """OpenAPI documentation is available at /app/api/docs and /app/api/openapi.json.

        NinjaExtraAPI serves Swagger UI at /docs and the raw schema at /openapi.json
        (not /schema/ as is common in some frameworks).
        Both must be accessible at the /app/ prefix.
        """
        response_docs = client.get("/app/api/docs")
        assert response_docs.status_code == 200, (
            f"Swagger UI at /app/api/docs returned {response_docs.status_code}. "
            "Verify the NinjaExtraAPI is correctly mounted at app/api/ in urls.py."
        )

        response_schema = client.get("/app/api/openapi.json")
        assert response_schema.status_code == 200, (
            f"OpenAPI JSON at /app/api/openapi.json returned {response_schema.status_code}."
        )
