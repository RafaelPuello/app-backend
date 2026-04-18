# CLAUDE.md - App Backend

This file provides backend-specific guidance. For frontend details and full service overview, see `/app/CLAUDE.md`.

## Project Overview

Django 6.0 backend API for the DigiDex app. Provides REST API for managing NFC tags, plant collections, and domain-specific data. Uses django-ninja for REST endpoints, django-modelcluster for clustered models, and supports authentication via JWT tokens from the ID service.

## Commands

### Setup & Development
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate          # Create database tables
python manage.py runserver 0.0.0.0:8000
```

### Testing
```bash
# Install dependencies (includes dev deps for testing)
pip install -r requirements.txt -r requirements-dev.txt

# Run all tests (uses config.settings_test via pytest.ini)
DJANGO_SETTINGS_MODULE=config.settings_test pytest

# Run routing tests only
DJANGO_SETTINGS_MODULE=config.settings_test pytest tests/test_routing.py -v

# Run tests for a specific app
DJANGO_SETTINGS_MODULE=config.settings_test pytest domain/ -v

# With coverage
DJANGO_SETTINGS_MODULE=config.settings_test pytest -v --cov

# Single test
DJANGO_SETTINGS_MODULE=config.settings_test pytest domain/tests.py::test_list_parity
```

**Test settings:** `config/settings_test.py` uses SQLite in-memory and loads the ID service JWT public key from `../../id/backend/config/keys/jwt_public_key.pem` (relative to repo root) for authenticating API test requests. Tests skip automatically if the key file is not found. The `DJANGO_SETTINGS_MODULE` env var must be set explicitly when running locally (the `.env.dev` file sets it to `config.settings` which requires PostgreSQL; override it on the command line as shown above).

**Python interpreter:** The venv at `backend/venv` uses Python 3.12.2 (from `/usr/local/`)
which lacks the compiled `_sqlite3` module on this host. Use the pyenv Python instead:
```bash
DJANGO_SETTINGS_MODULE=config.settings_test ~/.pyenv/versions/3.12.5/bin/pytest tests/test_routing.py -v
```

### Utilities
```bash
python manage.py createsuperuser  # Create admin user
python manage.py shell            # Django shell for manual testing
python manage.py makemigrations   # Create new migrations
python manage.py showmigrations   # Show migration status
```

## Architecture

### Application Structure

**Apps** (feature-based organization)
- `domain/` - Plant label models and NFC tag management (PlantLabel model)
- `nfctags/` - Abstract NFC tag base class and tag utilities
- `botany/` - Plant taxonomy and classification data

**API Endpoints** (via django-ninja-extra, mounted at `/app/api/`)
- `GET /app/api/nfctags?include=plant` - List NFC tags (paginated); `include=plant` adds plant details via select_related
- `POST /app/api/nfctags/register` - Register a new tag by UID
- `POST /app/api/nfctags/scan` - Look up a tag by ASCII mirror
- `GET /app/api/nfctags/{uuid}` - Retrieve a single NFC tag
- `PUT /app/api/nfctags/{uuid}` - Update tag fields
- `DELETE /app/api/nfctags/{uuid}` - Hard delete a tag
- `POST /app/api/nfctags/{uuid}/bind` - Bind tag to a plant (`{"plant_id": "<plant-uuid>"}`)
- `POST /app/api/nfctags/{uuid}/unbind` - Unbind tag from its plant
- `GET /app/api/gbif/{identifier}` - Fetch plant details from GBIF
- `GET /app/api/gbif/{identifier}/occurrences` - Paginated GBIF occurrences
- Swagger/OpenAPI: `GET /app/api/docs` (JSON schema: `GET /app/api/openapi.json`)

### Models

**NFC Tag Hierarchy**
```python
AbstractNFCTag (base class in nfctags)
  └── PlantLabel (domain)  # Concrete plant label implementation
```

Key fields:
- `uuid` - Unique identifier for tag (public-facing)
- `uid` - NFC tag UID/serial number (chip hardware ID)
- `plant` - FK to `botany.Plant` (null=True; set via `/bind` endpoint)
- Domain-specific fields (e.g., `title` for PlantLabel)

`NFC_TAG_MODEL = "domain.PlantLabel"` is set in `settings_test.py` and should be set in production settings to use `PlantLabel` as the concrete NFC tag model (as per ADR #0002).

**Path parameter annotation gotcha:** Django's `{uuid:param}` path converter returns a Python `uuid.UUID` object. When the endpoint also has a body parameter (e.g., `payload: BindPlantRequest`), pydantic v2 validates path params strictly — the path parameter **must** be annotated as `uuid.UUID` in the function signature, otherwise pydantic defaults it to `str` and raises 422.

Models use `django-modelcluster` for relational data clustering.

### API & Authentication

**Django-Ninja-Extra REST API** (`django-ninja-extra`)
- Class-based controllers: `DomainController` (nfctags) and `GBIFController` (plants)
- Mounted at `app/api/` in `config/urls.py` — full path `/app/api/*` handled by Django
- Swagger documentation auto-generated at `/app/api/docs` (raw JSON at `/app/api/openapi.json`)
- JWT Bearer authentication via `JWTAuthenticationBackend` (RS256, tokens from ID service)

**Why `/app/api/`?**
The frontend is served at `digidex.bio/app/`, and Traefik routes `/app/*` to the app backend without path stripping. Django receives the full path and routes it via the `app/api/` URL prefix.

**JWT Authentication** (Production and Development)
- Bearer tokens from the ID service (RS256-signed)
- Validated via `config/auth.py` using the ID service's public key
- Public key path configured via `JWT_PUBLIC_KEY_PATH` env var
- Session auth still used for Django admin and HTML views (domain/urls.py)

**JWT Token Flow**:
```
Frontend (app/frontend)
    ↓ POST /api/accounts/login
ID Service (id/backend)
    ↓ returns access_token, refresh_token
Frontend stores tokens in localStorage
    ↓ GET /app/api/nfctags/ (with Authorization: Bearer <access_token>)
App Backend (this service)
    ↓ Validates token using ID service's public key
    ↓ Returns authenticated user's data
```

**Token Validation in Code**:
```python
# In config/auth.py - JWTAuthenticationBackend validates tokens
from django_ninja_jwt.authentication import JWTAuthentication

# Tokens must include these claims:
# - sub: user UUID (subject)
# - exp: expiration time
# - iat: issued at time
# Token is verified using the ID service's public key (RS256 asymmetric)
```

**Adding JWT-Protected Endpoints**:
```python
# In app/api.py or feature app/api.py
from django_ninja_extra import api_controller, http_get
from django_ninja_jwt.authentication import JWTAuthentication

@api_controller("/plants", auth=JWTAuthentication())
class PlantController:
    @http_get("/my-plants/")
    def list_user_plants(self, request):
        """List plants owned by authenticated user"""
        user = request.user  # User from JWT token
        return {"plants": list(user.plants.values())}
```

**Public vs. Protected Endpoints**:
```python
@api_controller("/gbif")
class GBIFController:
    @http_get("/search/")
    def search_species(self, request, q: str):
        """Public endpoint - no auth required"""
        return gbif_service.search(q)

@api_controller("/nfctags", auth=JWTAuthentication())
class NFCTagController:
    @http_get("/")
    def list_tags(self, request):
        """Protected endpoint - requires valid JWT"""
        return NFCTag.objects.filter(user=request.user)
```

### Database

**Configuration**
- Uses `dj-database-url` to parse DATABASE_URL env var
- PostgreSQL in production, SQLite in development
- Connection pooling: `conn_max_age=600`, health checks enabled

## Testing

### Test Structure
- Test files: `domain/tests.py` and other app-level test files
- Framework: `pytest` with `pytest-django`
- Patterns: Factory fixtures, database state management, API parity testing

### Key Test Patterns
- `@pytest.mark.django_db` - Access to database in tests
- `client.login()` - Session-based authentication for tests
- API and HTML view parity tests (verify same data via different endpoints)
- User-scoped data creation via `NFCTagService(user=user)`

## Environment Variables

### Required
- `DJANGO_SECRET_KEY` - Secret key for Django
- `DATABASE_URL` - Database connection string (e.g., `postgresql://user:pass@localhost/dbname`)

### Optional (with defaults)
- `DJANGO_DEBUG` - Set to "True" for development (default: "False")
- `DJANGO_ALLOWED_HOSTS` - Comma-separated list of allowed hosts (default: "localhost")

### Development
- `.env.dev` file in `backend/` directory sets development variables
- `.env.prod` file for production settings

## Key Files

| File | Purpose |
|------|---------|
| `config/settings.py` | Main Django settings (database, installed apps, middleware) |
| `config/urls.py` | URL routing (admin, placeholder for API) |
| `config/wsgi.py` | WSGI application entry point |
| `config/asgi.py` | ASGI application entry point |
| `domain/models.py` | PlantLabel model (concrete NFC tag implementation) |
| `domain/tests.py` | Tests for domain app (list/detail parity, API checks) |
| `domain/views.py` | Django views (if any HTML views added) |
| `nfctags/models.py` | AbstractNFCTag base class |
| `botany/models.py` | Botanical/taxonomy data |
| `manage.py` | Django management command entry point |

## Routing Validation

The app backend's URL configuration enforces the Traefik routing contract: Traefik forwards
all `/app/*` paths to this service **without stripping the prefix**. Django must handle the full
path. If that contract is broken (e.g., someone adds a URL at `/admin/` instead of `/app/admin/`),
the routing will silently work in direct-access mode but fail behind Traefik.

### Health Check Endpoint

A public health check endpoint is registered on the `NinjaExtraAPI` instance in `config/urls.py`:

```
GET /app/api/health/
```

Returns `{"status": "ok", "service": "app-backend"}` with HTTP 200. No authentication required.

**Purpose:**
- Traefik health checks in production
- Docker Compose `healthcheck:` directives
- Monitoring and uptime checks
- Quick verification that the Django service is reachable through Traefik

### Routing Test Suite

`tests/test_routing.py` validates the routing contract with 7 tests:

| Test | What it verifies |
|------|-----------------|
| `test_health_check` | `GET /app/api/health/` returns `{"status": "ok", "service": "app-backend"}` |
| `test_nfctags_list_requires_auth` | `/app/api/nfctags` exists (not 404) and enforces auth (401) |
| `test_admin_accessible_at_app_prefix` | Admin is at `/app/admin/`, not bare `/admin/` |
| `test_admin_not_accessible_at_bare_path` | `/admin/` returns 404 (no path-stripping exposure) |
| `test_nfctags_direct_path_not_accessible` | `/nfctags/` returns 404 (no bare-path routes) |
| `test_health_check_no_auth_required` | Health check has no auth guard (public endpoint) |
| `test_api_docs_accessible` | Swagger UI at `/app/api/docs` and JSON schema at `/app/api/openapi.json` |

**Important:** NinjaExtraAPI serves docs at `/app/api/docs` and `/app/api/openapi.json` —
**not** `/app/api/schema/` (which returns 404). The CLAUDE.md "Inspect API Schema" section
previously referenced `/schema/`; the correct path is `/docs`.

Run routing tests:
```bash
DJANGO_SETTINGS_MODULE=config.settings_test pytest tests/test_routing.py -v
```

## Important Gotchas

### Settings Missing `import os`
The `config/settings.py` file references `os.environ` without importing `os`. Check that the import statement is present.

### Database URL Required
`dj-database-url` requires DATABASE_URL env var in production. Set it explicitly or the app will fail to start.

### Migration Management
Django migrations are version-controlled. Always commit migrations to git when changing models:
```bash
python manage.py makemigrations
git add */migrations/
git commit -m "Add new migration for ..."
```

### API vs HTML Views
The app currently provides API endpoints via django-ninja. HTML templates are not used; the frontend is a separate Next.js application.

## Deployment Notes

- **Database**: PostgreSQL required for production (not SQLite)
- **Static files**: Run `collectstatic` during build if serving static files from Django
- **Migrations**: Run `python manage.py migrate` on deployment to apply pending migrations
- **Debug mode**: Must be False in production (`DJANGO_DEBUG=False`)
- **Secret key**: Must be strong, unique, and secret; use secrets management system
- **WhiteNoise**: Not configured but can be added for static file serving from Django

## Common Tasks

### Add a New API Endpoint

**Step 1: Define the Model** (if needed)
```python
# app/nfctags/models.py
from django.db import models

class PlantLabel(models.Model):
    uuid = models.UUIDField(unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Step 2: Create Schema** (for serialization)
```python
# app/nfctags/schema.py
from ninja import Schema
from uuid import UUID

class PlantLabelOut(Schema):
    uuid: UUID
    title: str
    created_at: str
```

**Step 3: Create Controller** (django-ninja-extra)
```python
# app/nfctags/api.py
from django_ninja_extra import api_controller, http_get, http_post
from django_ninja_jwt.authentication import JWTAuthentication
from .models import PlantLabel
from .schema import PlantLabelOut

@api_controller("/nfctags", auth=JWTAuthentication())
class NFCTagController:
    @http_get("/", response=list[PlantLabelOut])
    def list_tags(self, request):
        """List all NFC tags for authenticated user"""
        return PlantLabel.objects.filter(user=request.user)
    
    @http_get("/{uuid}/", response=PlantLabelOut)
    def get_tag(self, request, uuid: str):
        """Get single NFC tag by UUID"""
        tag = PlantLabel.objects.get(uuid=uuid, user=request.user)
        return tag
    
    @http_post("/", response=PlantLabelOut)
    def create_tag(self, request, payload: PlantLabelOut):
        """Create new NFC tag"""
        tag = PlantLabel.objects.create(**payload.dict(), user=request.user)
        return tag
```

**Step 4: Register Controller**
```python
# app/config/api.py
from django_ninja_extra import NinjaExtraAPI
from ..nfctags.api import NFCTagController

api = NinjaExtraAPI()
api.register_controllers(NFCTagController)
```

**Step 5: Add to URL Configuration**
```python
# app/config/urls.py
from django.urls import path
from .api import api

urlpatterns = [
    path("app/api/", api.urls),  # Full path /app/api/*
]
```

**Step 6: Add Tests**
```python
# app/nfctags/tests.py
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
def test_list_nfctags(client):
    """Test listing NFC tags"""
    user = User.objects.create_user(email="test@example.com", password="test")
    client.force_authenticate(user)
    response = client.get("/app/api/nfctags/")
    assert response.status_code == 200
    assert response.json() == []
```

### Add Tests

```bash
cd backend
pytest domain/tests.py::test_your_test_name -v
```

### Check Database State

```bash
python manage.py shell
>>> from domain.models import PlantLabel
>>> PlantLabel.objects.all()
```

### Inspect API Schema

Start the server and visit `http://localhost:8000/app/api/docs` for Swagger UI.
Raw OpenAPI JSON is at `http://localhost:8000/app/api/openapi.json`.

**Note:** The API is at `/app/api/` (not `/api/`) because Traefik does not strip the `/app` path prefix — Django receives and handles the full path.
