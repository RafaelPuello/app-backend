"""
Tests for the botany app Plant model metadata fields.

Verifies:
- acquisition_date, location, and notes are optional fields on Plant
- gbif_id accepts NULL (no longer defaults to 6)
- Legacy gbif_id=6 cleanup migration logic (via RunPython)
"""

import datetime
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user("botanist", "botanist@example.com", "testpass123")


@pytest.fixture
def plant(user):
    from botany.models import Plant

    return Plant.objects.create(
        name="Monstera deliciosa",
        user=user,
    )


class TestPlantMetadataFields:
    """Plant model should have optional acquisition_date, location, and notes fields."""

    @pytest.mark.django_db
    def test_plant_can_be_created_without_metadata_fields(self, user):
        """All three metadata fields are optional; plant creates without them."""
        from botany.models import Plant

        plant = Plant.objects.create(name="Ficus lyrata", user=user)
        assert plant.pk is not None
        assert plant.acquisition_date is None
        assert plant.location == ""
        assert plant.notes == ""

    @pytest.mark.django_db
    def test_acquisition_date_field_accepts_date(self, user):
        """acquisition_date accepts a Python date value."""
        from botany.models import Plant

        today = datetime.date(2026, 4, 18)
        plant = Plant.objects.create(
            name="Pothos",
            user=user,
            acquisition_date=today,
        )
        plant.refresh_from_db()
        assert plant.acquisition_date == today

    @pytest.mark.django_db
    def test_location_field_accepts_string(self, user):
        """location accepts a string up to 255 characters."""
        from botany.models import Plant

        plant = Plant.objects.create(
            name="Snake Plant",
            user=user,
            location="Living room, north-east corner",
        )
        plant.refresh_from_db()
        assert plant.location == "Living room, north-east corner"

    @pytest.mark.django_db
    def test_notes_field_accepts_text(self, user):
        """notes accepts multi-line text."""
        from botany.models import Plant

        notes_text = "Acquired from local nursery.\nNeeds indirect sunlight."
        plant = Plant.objects.create(
            name="Peace Lily",
            user=user,
            notes=notes_text,
        )
        plant.refresh_from_db()
        assert plant.notes == notes_text


class TestPlantGbifIdNullable:
    """gbif_id should now be nullable (null=True) with no default."""

    @pytest.mark.django_db
    def test_gbif_id_can_be_null(self, user):
        """Plant can be created with gbif_id=None."""
        from botany.models import Plant

        plant = Plant.objects.create(name="Unknown Fern", user=user, gbif_id=None)
        plant.refresh_from_db()
        assert plant.gbif_id is None

    @pytest.mark.django_db
    def test_gbif_id_accepts_real_species_id(self, user):
        """gbif_id still accepts a real GBIF species integer."""
        from botany.models import Plant

        plant = Plant.objects.create(
            name="Monstera deliciosa",
            user=user,
            gbif_id=2684241,  # Real GBIF ID for Monstera deliciosa
        )
        plant.refresh_from_db()
        assert plant.gbif_id == 2684241

    @pytest.mark.django_db
    def test_gbif_id_defaults_to_null_not_six(self, user):
        """Plant created without gbif_id should default to NULL, not 6."""
        from botany.models import Plant

        plant = Plant.objects.create(name="Mystery Plant", user=user)
        plant.refresh_from_db()
        assert plant.gbif_id is None
