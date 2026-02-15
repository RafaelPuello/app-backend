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
pip install -r requirements.txt   # Ensure test dependencies installed
pytest                            # Run all tests
pytest domain/                    # Run tests for domain app only
pytest -v                         # Verbose output
pytest -v --cov                   # With coverage report
pytest domain/tests.py::test_list_parity  # Single test
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

**API Endpoints** (via django-ninja)
- `/api/nfctags` - List, create, retrieve, update NFC tags
- `/api/` - Root API endpoint with Swagger documentation

### Models

**NFC Tag Hierarchy**
```python
AbstractNFCTag (base class in nfctags)
  └── PlantLabel (domain)  # Concrete plant label implementation
```

Key fields:
- `uuid` - Unique identifier for tag
- `uid` - NFC tag UID/serial number
- Domain-specific fields (e.g., `title` for PlantLabel)

Models use `django-modelcluster` for relational data clustering.

### API & Authentication

**Django-Ninja REST API**
- Standard REST conventions (GET/POST/PUT/DELETE)
- Swagger documentation auto-generated at `/api/schema/`
- Can integrate with JWT tokens from ID service (optional, currently uses session auth in dev)

**Session Authentication** (Development)
- Uses Django's standard session authentication
- Credentials passed via login endpoint
- Sessions managed via cookies

**Future JWT Integration**
- ID service provides RS256 JWT tokens
- API can validate tokens using public key from ID service
- Implement custom authentication backend for production

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

1. Create model in appropriate app (e.g., `domain/models.py`)
2. Create django-ninja router and views
3. Register router in URL configuration
4. Add tests for endpoint

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

Start the server and visit `http://localhost:8000/api/schema/` for Swagger UI.
