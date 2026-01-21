"""
Management command to check system health and send alerts if needed.
Can be run via cron job for automated monitoring.
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from app.core.monitoring import check_health, should_send_alert
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check system health and send email alerts if issues are detected"

    def add_arguments(self, parser):
        parser.add_argument(
            "--send-alerts",
            action="store_true",
            help="Send email alerts if issues are detected",
        )
        parser.add_argument(
            "--alert-email",
            type=str,
            help="Email address to send alerts to (defaults to DEFAULT_FROM_EMAIL)",
        )

    def handle(self, *args, **options):
        send_alerts = options.get("send_alerts", False)
        alert_email = options.get("alert_email") or settings.DEFAULT_FROM_EMAIL

        self.stdout.write("Checking system health...")
        health_data = check_health()

        # Print health status
        self.stdout.write(f"\nStatus: {health_data['status']}")
        self.stdout.write(f"Database: {health_data['database']['status']}")
        self.stdout.write(f"Cache: {health_data['cache']['status']}")
        self.stdout.write(f"Disk: {health_data['disk']['status']} ({health_data['disk'].get('percent_used', 0):.1f}% used)")

        # Check if alerts should be sent
        should_alert, alert_type = should_send_alert(health_data)

        if should_alert and send_alerts:
            self.stdout.write(f"\n⚠️  Alert condition detected: {alert_type}")
            self._send_alert(health_data, alert_type, alert_email)
        elif should_alert:
            self.stdout.write(f"\n⚠️  Alert condition detected: {alert_type} (use --send-alerts to send email)")
        else:
            self.stdout.write("\n✅ All systems healthy")

    def _send_alert(self, health_data, alert_type, email):
        """Send email alert about system health issues."""
        try:
            subject = f"[Kuafora] System Alert: {alert_type}"
            
            # Build email body
            body_lines = [
                f"System Health Alert: {alert_type}",
                "",
                f"Status: {health_data['status']}",
                f"Timestamp: {health_data.get('timestamp', 'N/A')}",
                "",
                "Details:",
                f"- Database: {health_data['database']['status']}",
                f"- Cache: {health_data['cache']['status']}",
                f"- Disk: {health_data['disk']['status']}",
            ]

            # Add disk details if available
            disk = health_data.get("disk", {})
            if "percent_used" in disk:
                body_lines.append(f"- Disk Usage: {disk['percent_used']:.1f}% ({disk.get('used_gb', 0):.1f}GB / {disk.get('total_gb', 0):.1f}GB)")

            # Add database error if present
            if health_data["database"].get("error"):
                body_lines.append(f"- Database Error: {health_data['database']['error']}")

            body = "\n".join(body_lines)

            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            self.stdout.write(self.style.SUCCESS(f"✅ Alert sent to {email}"))
            logger.info(f"Health alert sent to {email}: {alert_type}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to send alert: {e}"))
            logger.error(f"Failed to send health alert: {e}", exc_info=True)

