# Generated manually for EmailDailyLog (günlük e-posta sayacı ve 400 limit uyarısı)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_user_phone_encryption"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailDailyLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True, unique=True)),
                ("count", models.PositiveIntegerField(default=0)),
                ("alert_sent", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "Günlük e-posta logu",
                "verbose_name_plural": "Günlük e-posta logları",
            },
        ),
    ]
