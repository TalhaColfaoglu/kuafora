from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="hold",
            name="service_items",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="hold",
            name="price_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]

