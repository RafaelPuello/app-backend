from django.core.management.base import BaseCommand
from django.db import transaction

from nfctags import get_nfctag_model
from nfctags.models import NFCTag

NewNFCTagModel = get_nfctag_model()


class Command(BaseCommand):
    help = ('Migrate data from NFCTag to the new model.\n')

    def handle(self, *args, **options):
        nfctags_created = 0
        nfctags_existing = 0

        with transaction.atomic():
            # --- NFCTag Migration ---
            nfctags = NFCTag.objects.all()
            for nfc in nfctags:
                _, created = NewNFCTagModel.objects.get_or_create(
                    uid=nfc.uid,
                    defaults={
                        "uuid": nfc.uuid,
                        "user": nfc.user,
                    },
                )
                if created:
                    nfctags_created += 1
                else:
                    nfctags_existing += 1

        # --- Output Summary ---
        self.stdout.write(self.style.SUCCESS(
            f"Migration complete!\n"
            f"NFCTags → Created: {nfctags_created}, Existing: {nfctags_existing}\n"
        ))
