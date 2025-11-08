from django.db import migrations
from django.db.models import F, Q
from django.db.models.expressions import Func
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators, DateTimeRangeField
from django.contrib.postgres.operations import BtreeGistExtension

from app.appointments.models import AppointmentStatus


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0002_hold_service_items"),
    ]

    operations = [
        # Ensure required extension for GIST equality on non-range columns
        BtreeGistExtension(),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=ExclusionConstraint(
                name="exclude_overlap_per_staff_active",
                expressions=[
                    (Func(F("start_datetime"), F("end_datetime"), function="tstzrange", output_field=DateTimeRangeField()), RangeOperators.OVERLAPS),
                    (F("staff"), RangeOperators.EQUAL),
                ],
                condition=Q(
                    status__in=[
                        AppointmentStatus.PENDING,
                        AppointmentStatus.CONFIRMED,
                        AppointmentStatus.SUGGESTED,
                    ]
                ),
                index_type="GIST",
            ),
        ),
    ]


