from django.db import migrations, models
from django.db.models import Count, Max, Sum, Q


def dedupe_guest_activity_logs(apps, schema_editor):
    """
    Guest (user=NULL) activity loglarında (device_id, activity_date, app_type) bazında
    duplicate kayıtları birleştirip tek kayda düşürür.
    """
    UserActivityLog = apps.get_model("analytics", "UserActivityLog")

    dup_groups = (
        UserActivityLog.objects.filter(user__isnull=True)
        .values("device_id", "activity_date", "app_type")
        .annotate(
            c=Count("id"),
            sum_login=Sum("login_count"),
            max_last=Max("last_activity"),
        )
        .filter(c__gt=1)
    )

    for g in dup_groups.iterator():
        device_id = g["device_id"]
        activity_date = g["activity_date"]
        app_type = g["app_type"]

        logs = (
            UserActivityLog.objects.filter(
                user__isnull=True,
                device_id=device_id,
                activity_date=activity_date,
                app_type=app_type,
            )
            .order_by("id")
        )
        keep = logs.first()
        if not keep:
            continue

        UserActivityLog.objects.filter(pk=keep.pk).update(
            login_count=g["sum_login"] or keep.login_count,
            last_activity=g["max_last"] or keep.last_activity,
        )

        logs.exclude(pk=keep.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0002_useractivitylog_dailymetrics"),
    ]

    operations = [
        migrations.RunPython(dedupe_guest_activity_logs, reverse_code=migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="useractivitylog",
            constraint=models.UniqueConstraint(
                fields=["device_id", "activity_date", "app_type"],
                condition=Q(user__isnull=True),
                name="uniq_guest_device_day_app",
            ),
        ),
    ]

