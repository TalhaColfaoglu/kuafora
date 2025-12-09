from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("booking", "Randevu"),
                    ("chat", "Mesaj"),
                    ("reply", "Yorum Yanıtı"),
                    ("system", "Sistem"),
                ],
                max_length=20,
            ),
        ),
    ]


