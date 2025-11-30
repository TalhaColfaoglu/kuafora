from __future__ import annotations

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0015_schedulechangerequest_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffworkinghours",
            name="valid_from",
            field=models.DateField(default=datetime.date(2020, 1, 1)),
        ),
        migrations.AddField(
            model_name="staffworkinghours",
            name="valid_until",
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AlterUniqueTogether(
            name="staffworkinghours",
            unique_together={("staff", "day_of_week", "valid_from")},
        ),
    ]


