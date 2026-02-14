from django.db import models


class NFCTagQuerySet(models.QuerySet):
    def available(self):
        """
        NFC tags that are active and unassigned to a user.
        """
        return self.filter(active=True, user__isnull=True)

    def assigned(self):
        """
        NFC tags that have a user associated.
        """
        return self.filter(active=True, user__isnull=False)

    def linked(self):
        """
        NFC tags that are linked to a content_object.
        """
        return self.filter(active=True, content_type__isnull=False, object_id__isnull=False)

    def unlinked(self):
        """
        NFC tags not currently linked to a content_object.
        """
        return self.filter(active=True, content_type__isnull=True, object_id__isnull=True)


class NFCTagManager(models.Manager):
    def get_queryset(self):
        return NFCTagQuerySet(self.model, using=self._db)

    def available(self):
        return self.get_queryset().available()

    def assigned(self):
        return self.get_queryset().assigned()

    def linked(self):
        return self.get_queryset().linked()

    def unlinked(self):
        return self.get_queryset().unlinked()
