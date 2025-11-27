from __future__ import annotations

from django.db import migrations, models


def create_schedulechangerequest_table(apps, schema_editor):
    table_name = "barbers_schedulechangerequest"
    if table_name in schema_editor.connection.introspection.table_names():
        return
    ScheduleChangeRequest = apps.get_model("barbers", "ScheduleChangeRequest")
    schema_editor.create_model(ScheduleChangeRequest)


def drop_schedulechangerequest_table(apps, schema_editor):
    table_name = "barbers_schedulechangerequest"
    if table_name not in schema_editor.connection.introspection.table_names():
        return
    ScheduleChangeRequest = apps.get_model("barbers", "ScheduleChangeRequest")
    schema_editor.delete_model(ScheduleChangeRequest)


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0014_breakwindow"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
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
                )
            ],
            database_operations=[
                migrations.RunPython(
                    code=create_schedulechangerequest_table,
                    reverse_code=drop_schedulechangerequest_table,
                )
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameIndex(
                    model_name="breakwindow",
                    new_name="barbers_bre_barbers_3d472a_idx",
                    old_name="barbershop_date_break_idx",
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER INDEX IF EXISTS barbershop_date_break_idx RENAME TO barbers_bre_barbers_3d472a_idx;",
                    reverse_sql="ALTER INDEX IF EXISTS barbers_bre_barbers_3d472a_idx RENAME TO barbershop_date_break_idx;",
                )
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameIndex(
                    model_name="breakwindow",
                    new_name="barbers_bre_staff_i_1aeaf4_idx",
                    old_name="staff_date_break_idx",
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER INDEX IF EXISTS staff_date_break_idx RENAME TO barbers_bre_staff_i_1aeaf4_idx;",
                    reverse_sql="ALTER INDEX IF EXISTS barbers_bre_staff_i_1aeaf4_idx RENAME TO staff_date_break_idx;",
                )
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="shopworkinghours",
                    name="break_start_time",
                    field=models.TimeField(blank=True, null=True),
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE barbers_shopworkinghours ADD COLUMN IF NOT EXISTS break_start_time time;",
                    reverse_sql="ALTER TABLE barbers_shopworkinghours DROP COLUMN IF EXISTS break_start_time;",
                )
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="shopworkinghours",
                    name="break_end_time",
                    field=models.TimeField(blank=True, null=True),
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE barbers_shopworkinghours ADD COLUMN IF NOT EXISTS break_end_time time;",
                    reverse_sql="ALTER TABLE barbers_shopworkinghours DROP COLUMN IF EXISTS break_end_time;",
                )
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="staffworkinghours",
                    name="break_start_time",
                    field=models.TimeField(blank=True, null=True),
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE barbers_staffworkinghours ADD COLUMN IF NOT EXISTS break_start_time time;",
                    reverse_sql="ALTER TABLE barbers_staffworkinghours DROP COLUMN IF EXISTS break_start_time;",
                )
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="staffworkinghours",
                    name="break_end_time",
                    field=models.TimeField(blank=True, null=True),
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE barbers_staffworkinghours ADD COLUMN IF NOT EXISTS break_end_time time;",
                    reverse_sql="ALTER TABLE barbers_staffworkinghours DROP COLUMN IF EXISTS break_end_time;",
                )
            ],
        ),
    ]


