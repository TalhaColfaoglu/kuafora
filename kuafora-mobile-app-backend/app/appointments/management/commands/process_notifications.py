from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import utils as db_utils
from time import sleep

from app.appointments.models import NotificationEvent


class Command(BaseCommand):
    help = "Process pending notification events and mark them as sent. Placeholder sender."

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process once and exit')

    def handle(self, *args, **options):
        once = options.get('once')
        while True:
            processed = 0
            try:
                with transaction.atomic():
                    events = list(
                        NotificationEvent.objects
                        .select_for_update(skip_locked=True)
                        .filter(status=NotificationEvent.Status.PENDING)[:100]
                    )
                    for ev in events:
                        # Push provider is not configured; keep as a safe no-op sender.
                        ev.status = NotificationEvent.Status.SENT
                        ev.save(update_fields=["status"])
                        processed += 1
            except (db_utils.ProgrammingError, db_utils.OperationalError):
                # DB hazır değil veya tablo yok; kısa bekleyip tekrar dene
                sleep(2)
                if once:
                    break
                continue
            if once:
                self.stdout.write(self.style.SUCCESS(f"Processed {processed} events"))
                break
            sleep(2)


