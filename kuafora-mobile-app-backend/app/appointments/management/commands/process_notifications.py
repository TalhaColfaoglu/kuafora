from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import utils as db_utils
from time import sleep

from app.appointments.models import NotificationEvent
from app.notifications.push import active_tokens_for_users, send_push_to_tokens


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
                        try:
                            payload = ev.payload or {}
                            user_ids = payload.get("user_ids") or []
                            title = (payload.get("title") or "").strip()
                            body = (payload.get("body") or "").strip()
                            data = payload.get("data") or {}
                            # Ensure all data values are strings for FCM.
                            data = {str(k): str(v) for k, v in data.items()}

                            tokens = active_tokens_for_users(user_ids)
                            if tokens and title and body:
                                send_push_to_tokens(tokens, title=title, body=body, data=data)
                            ev.status = NotificationEvent.Status.SENT
                            ev.last_error = ""
                            ev.save(update_fields=["status", "last_error", "updated_at"])
                            processed += 1
                        except Exception as e:
                            ev.status = NotificationEvent.Status.FAILED
                            ev.retries = (ev.retries or 0) + 1
                            ev.last_error = str(e)[:2000]
                            ev.save(update_fields=["status", "retries", "last_error", "updated_at"])
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


