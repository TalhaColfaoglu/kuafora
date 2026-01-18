from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0009_email_verification_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="requires_email_verification",
            field=models.BooleanField(default=False),
        ),
    ]


