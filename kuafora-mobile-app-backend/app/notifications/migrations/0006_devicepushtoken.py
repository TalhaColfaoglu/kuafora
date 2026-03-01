from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_partner_notification_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="DevicePushToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, max_length=255)),
                ("platform", models.CharField(choices=[("android", "Android"), ("ios", "iOS"), ("web", "Web")], max_length=12)),
                ("device_id", models.CharField(blank=True, default="", help_text="Client-generated stable device id (optional).", max_length=120)),
                ("app_version", models.CharField(blank=True, default="", max_length=40)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="push_tokens", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Push Token",
                "verbose_name_plural": "Push Tokens",
            },
        ),
        migrations.AddIndex(
            model_name="devicepushtoken",
            index=models.Index(fields=["user", "is_active"], name="notificatio_user_id_8e3d5a_idx"),
        ),
        migrations.AddIndex(
            model_name="devicepushtoken",
            index=models.Index(fields=["token", "is_active"], name="notificatio_token_9e6a22_idx"),
        ),
        migrations.AddConstraint(
            model_name="devicepushtoken",
            constraint=models.UniqueConstraint(fields=("user", "token"), name="unique_user_token"),
        ),
    ]

