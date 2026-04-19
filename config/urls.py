"""
URL configuration for the DigiDex App backend.

API is mounted at 'app/api/' to match subdirectory routing:
- Traefik routes /app/* to this backend without path stripping
- Django receives the full path /app/api/* and handles it here

See: https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from ninja_extra import NinjaExtraAPI

from botany.api import GBIFController, PlantSearchController
from domain.api import DomainController

api = NinjaExtraAPI(
    title="DigiDex App API",
    version="1.0.0",
    description="REST API for NFC tag management and botanical data.",
    urls_namespace="app_api",
)
api.register_controllers(DomainController, GBIFController, PlantSearchController)


@api.get("/health/", auth=None, tags=["Health"])
def health_check(request):
    """Health check endpoint for monitoring and Traefik health checks"""
    return {"status": "ok", "service": "app-backend"}


urlpatterns = [
    path("app/admin/", admin.site.urls),
    path("app/api/", api.urls),
    path("app/nfctags/", include("domain.urls")),
]
