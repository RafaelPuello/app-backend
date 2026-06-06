# CLAUDE.md - App Backend

Django 6.0 REST API for NFC tag management, plant discovery (Pokedex via GBIF), and collections. Uses django-ninja for REST endpoints, JWT authentication from ID service.

For full service overview, see `/app/CLAUDE.md`. For setup and command reference, see README.md.

## Architecture

### Application Structure

**Apps** (feature-based organization)
- `domain/` - Plant label models and NFC tag management (PlantLabel model)
- `nfctags/` - Abstract NFC tag base class and tag utilities
- `botany/` - Plant taxonomy and classification data

**API Endpoints** (via django-ninja-extra, mounted at `/app/api/`)

*NFC Tag Management:*
- `GET /app/api/nfctags?include=plant` - List NFC tags (paginated); `include=plant` adds plant details via select_related
- `POST /app/api/nfctags/register` - Register a new tag by UID
- `POST /app/api/nfctags/scan` - Look up a tag by ASCII mirror
- `GET /app/api/nfctags/{uuid}` - Retrieve a single NFC tag
- `PUT /app/api/nfctags/{uuid}` - Update tag fields
- `DELETE /app/api/nfctags/{uuid}` - Hard delete a tag
- `POST /app/api/nfctags/{uuid}/bind` - Bind tag to a plant (`{"plant_id": "<plant-uuid>"}`)
- `POST /app/api/nfctags/{uuid}/unbind` - Unbind tag from its plant

*Pokedex Feature (Plant Catalog & Discovery):*
- `GET /app/api/plants?search=query` - Search curated plant seed database (MVP: initial seed data)
- `GET /app/api/plants/{plant_id}` - Retrieve plant details (scientific name, taxonomy, descriptions)
- `GET /app/api/gbif/search?q=query` - Search GBIF species database (public, no auth required)
- `GET /app/api/gbif/{gbif_key}` - Fetch detailed plant information from GBIF (taxonomy, common names, specimen count)
- `GET /app/api/gbif/{gbif_key}/occurrences?limit=10` - Get paginated specimen occurrence records from GBIF (geographic distribution)

*Documentation & Health:*
- `GET /app/api/docs` - Swagger/OpenAPI interactive documentation
- `GET /app/api/openapi.json` - OpenAPI schema JSON
- `GET /app/api/health/` - Health check endpoint (no auth required)

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

### Pokedex Feature (Plant Catalog & Discovery)

The Pokedex feature provides a plant catalog and discovery interface combining:
- **Curated Seed Data**: Initial set of popular/common plants stored in the `botany.Plant` model
- **GBIF Integration**: Real-time plant discovery via GBIF (Global Biodiversity Information Facility) API

**Plant Model** (`botany/models.py`):
- `Plant` model with fields: `gbif_key` (GBIF ID), `scientific_name`, `common_name`, `description`, `image_url`
- Searchable by plant name, family, or GBIF taxonomy
- Relationships: can be bound to multiple NFC tags via PlantLabel

**Plant Metadata** (stored in database):
- **Taxonomy**: Scientific classification (kingdom, phylum, class, order, family, genus, species)
- **Common Names**: Multiple common names by region/language
- **Descriptions**: Plant characteristics, habitat, uses
- **Images**: Plant photos for visual identification

**GBIF Integration** (`botany/services.py` or similar):
- `gbif_search(query)` - Search GBIF taxonomy by name/keyword (public API, no auth)
- `gbif_fetch(gbif_key)` - Fetch detailed plant data from GBIF including taxonomy and occurrence data
- `gbif_occurrences(gbif_key)` - Fetch specimen occurrence records (geographic distribution, observation dates)

**Use Cases**:
1. **Browse Plant Catalog**: User opens Pokedex, browses curated plant database
2. **Search by Name**: User searches for plant by common/scientific name (searches local seed + GBIF)
3. **Discover Plants**: User explores GBIF for plants matching criteria (family, habitat, etc.)
4. **Bind Plant to Tag**: User selects plant from catalog, binds to NFC tag via `/bind` endpoint
5. **View Plant Details**: User scans NFC tag, sees linked plant info (metadata from local DB or GBIF)

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

## Conventions

- **App structure**: Feature-based (domain/, nfctags/, botany/); models, API controllers, tests in each app
- **Migrations**: Always version-controlled in `*/migrations/`; never modify applied migrations
- **UUIDs**: Public-facing; internal models use auto-increment IDs
- **Authentication**: JWT (RS256) for API; session auth for admin UI
- **Database queries**: Use `select_related`/`prefetch_related` to prevent N+1; test coverage required
- **Type hints**: All signatures must be typed; use `uuid.UUID` for path parameters (pydantic v2 strict mode)

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

The app backend's URL configuration enforces the Traefik routing contract: Traefik forwards all `/app/*` paths to this service **without stripping the prefix**. Django must handle the full path. See `.claude/rules/traefik-path-handling.md` for the complete contract and common mistakes. If broken, the routing will silently work in direct-access mode but fail behind Traefik.

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

## Gotchas

- **Path parameter type annotations**: When endpoint has both path param and body param, path param must be annotated as `uuid.UUID` (not `str`). Pydantic v2 strict mode rejects unannotated params.
- **JWT token claims**: Tokens must include `sub` (user UUID, not email), `exp`, `iat`. Validated with RS256 asymmetric key.
- **Migrations immutable**: Never modify applied migrations. Create new ones if changes are needed.
- **Database query performance**: All model lists must use `select_related()`/`prefetch_related()` to prevent N+1. Tests should verify this.
- **Settings import**: Ensure `import os` is present in `config/settings.py` (referenced by env vars).
- **API path**: Must be mounted at `/app/api/` in URL config, not `/api/`. Traefik forwards full path without stripping.
