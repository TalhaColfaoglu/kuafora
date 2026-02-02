"""
Partner uygulaması bildirim ağı: ödeme hatırlatması ve abonelik bitişi bildirimleri.
Cron ile günlük çalıştırılabilir (örn: 0 9 * * *).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from app.subscriptions.models import Subscription
from app.notifications.utils import (
    notify_shop_admins_about_payment_reminder,
    notify_shop_admins_about_subscription_expiry,
)
from app.notifications.models import Notification


class Command(BaseCommand):
    help = "Ödeme zamanı ve abonelik bitişi için partner bildirimleri gönderir (günlük çalıştırın)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Sadece hangi aboneliklere gideceğini listele, gönderme.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        today = timezone.now().date()
        payment_reminder_cutoff = today + timedelta(days=7)
        expiry_warning_days = 3

        # Aktif abonelikler (trial, active, grace_period); lifetime hariç
        qs = Subscription.objects.filter(
            status__in=["trial", "active", "grace_period"]
        ).select_related("barbershop", "plan")

        payment_sent = 0
        expiry_sent = 0

        for sub in qs:
            shop = sub.barbershop
            plan_name = sub.plan.name if sub.plan_id else "Abonelik"

            # Ödeme hatırlatması: current_period_end 7 gün içindeyse
            if sub.current_period_end:
                end_date = sub.current_period_end.date() if hasattr(sub.current_period_end, "date") else sub.current_period_end
                days_left = (end_date - today).days
                if 1 <= days_left <= 7:
                    if dry_run:
                        self.stdout.write(
                            f"  [payment_reminder] {shop.name} (ID {sub.id}) – {days_left} gün kaldı"
                        )
                        payment_sent += 1
                        continue
                    # Aynı gün zaten bu abonelik için ödeme hatırlatması gönderilmiş mi?
                    if not Notification.objects.filter(
                        type="payment_reminder",
                        reference_id=str(sub.id),
                        created_at__date=today,
                    ).exists():
                        n = notify_shop_admins_about_payment_reminder(
                            subscription=sub,
                            title="Ödeme hatırlatması",
                            body=f"{shop.name} – {plan_name} aboneliğinizin ödeme tarihi {end_date} ({days_left} gün kaldı).",
                        )
                        if n > 0:
                            payment_sent += 1
                            # İsteğe bağlı: reference_id ile tekrar gönderimi engellemek için
                            # Notification'da reference_id kullanıyoruz; API'de zaten sub.id kullanılıyor.
                            # Farklı bir ref kullanırsak duplicate kontrolü yapabiliriz.
                            # Şimdilik her abonelik için bir kez gönderiyoruz (günlük bir kez çalıştığında yeterli).

                # Abonelik bitişi uyarısı: 3 gün veya daha az kaldıysa
                if 0 <= days_left <= expiry_warning_days:
                    if dry_run:
                        self.stdout.write(
                            f"  [subscription_expiry] {shop.name} (ID {sub.id}) – {days_left} gün kaldı"
                        )
                        expiry_sent += 1
                        continue
                    if not Notification.objects.filter(
                        type="subscription_expiry",
                        reference_id=str(sub.id),
                        created_at__date=today,
                    ).exists():
                        n = notify_shop_admins_about_subscription_expiry(
                            subscription=sub,
                            title="Abonelik süresi doluyor",
                            body=f"{shop.name} – {plan_name} aboneliğiniz {end_date} tarihinde sona erecek ({days_left} gün kaldı).",
                        )
                        if n > 0:
                            expiry_sent += 1

            # Trial bitişi: trial_ends_at 7 gün içindeyse de hatırlat
            if sub.status == "trial" and sub.trial_ends_at:
                trial_end = sub.trial_ends_at.date() if hasattr(sub.trial_ends_at, "date") else sub.trial_ends_at
                days_left = (trial_end - today).days
                if 1 <= days_left <= 7:
                    if dry_run:
                        self.stdout.write(
                            f"  [subscription_expiry] {shop.name} (trial, ID {sub.id}) – {days_left} gün kaldı"
                        )
                        expiry_sent += 1
                        continue
                    if not Notification.objects.filter(
                        type="subscription_expiry",
                        reference_id=str(sub.id),
                        created_at__date=today,
                    ).exists():
                        n = notify_shop_admins_about_subscription_expiry(
                            subscription=sub,
                            title="Deneme süresi doluyor",
                            body=f"{shop.name} – Deneme süreniz {trial_end} tarihinde bitiyor ({days_left} gün kaldı).",
                        )
                        if n > 0:
                            expiry_sent += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry-run: {payment_sent} ödeme hatırlatması, {expiry_sent} bitiş uyarısı gönderilecekti."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Gönderilen: {payment_sent} ödeme hatırlatması, {expiry_sent} abonelik bitişi uyarısı."))
