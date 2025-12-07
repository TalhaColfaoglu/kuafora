from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0014_breakwindow"),
    ]

    operations = [
                migrations.CreateModel(
                    name="ScheduleChangeRequest",
                    fields=[
                        (
                            "id",
                            models.AutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "target_type",
                            models.CharField(
                                choices=[("shop", "Shop"), ("staff", "Staff")],
                                max_length=10,
                            ),
                        ),
                        ("target_id", models.IntegerField(help_text="Staff ID veya Barbershop ID")),
                        ("new_schedule_json", models.JSONField(help_text="Uygulanacak yeni saat verisi (list of dicts)")),
                        ("effective_date", models.DateField()),
                        ("applied", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        "indexes": [
                            models.Index(
                                fields=["target_type", "target_id"],
                                name="barbers_sch_target__40ec22_idx",
                            ),
                            models.Index(
                                fields=["effective_date", "applied"],
                                name="barbers_sch_effecti_11d4cf_idx",
                            ),
                        ],
                    },
        ),
                migrations.RenameIndex(
                    model_name="breakwindow",
                    new_name="barbers_bre_barbers_3d472a_idx",
                    old_name="barbershop_date_break_idx",
        ),
                migrations.RenameIndex(
                    model_name="breakwindow",
                    new_name="barbers_bre_staff_i_1aeaf4_idx",
                    old_name="staff_date_break_idx",
        ),
                migrations.AddField(
                    model_name="shopworkinghours",
                    name="break_start_time",
                    field=models.TimeField(blank=True, null=True),
        ),
                migrations.AddField(
                    model_name="shopworkinghours",
                    name="break_end_time",
                    field=models.TimeField(blank=True, null=True),
        ),
                migrations.AddField(
                    model_name="staffworkinghours",
                    name="break_start_time",
                    field=models.TimeField(blank=True, null=True),
        ),
                migrations.AddField(
                    model_name="staffworkinghours",
                    name="break_end_time",
                    field=models.TimeField(blank=True, null=True),
        ),
    ]
