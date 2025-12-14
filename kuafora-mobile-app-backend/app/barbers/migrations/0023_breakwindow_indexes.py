# Generated manually: add indexes for break window queries (calendar performance)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0022_add_review_likes_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="breakwindow",
            index=models.Index(fields=["barbershop", "scope", "date", "start_time"], name="bw_shop_scope_date_start"),
        ),
        migrations.AddIndex(
            model_name="breakwindow",
            index=models.Index(fields=["staff", "date", "start_time"], name="bw_staff_date_start"),
        ),
    ]


