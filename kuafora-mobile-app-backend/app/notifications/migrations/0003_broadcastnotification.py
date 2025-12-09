from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_alter_notification_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="BroadcastNotification",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField()),
                (
                    "segment",
                    models.CharField(
                        choices=[
                            ("all_users", "Tüm kullanıcılar"),
                            ("active_30_days", "Son 30 günde aktif olanlar"),
                        ],
                        default="all_users",
                        help_text="Kime gideceğini seçin. Örn: 'Tüm kullanıcılar' ya da 'Son 30 günde aktif olanlar'.",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "sent_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Bildirimler üretildiğinde sistem tarafından otomatik doldurulur.",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Toplu Bildirim (admin)",
                "verbose_name_plural": "Toplu Bildirimler (admin)",
                "ordering": ["-created_at"],
            },
        ),
    ]


