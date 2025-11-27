from django.conf import settings
from django.db import migrations, models
from django.db.utils import ProgrammingError
import django.db.models.deletion
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db.models import F, Func, Q


def create_customerban_table(apps, schema_editor):
    table_name = "appointments_customerban"
    if table_name in schema_editor.connection.introspection.table_names():
        return
    CustomerBan = apps.get_model("appointments", "CustomerBan")
    try:
        schema_editor.create_model(CustomerBan)
    except ProgrammingError as exc:
        message = str(exc).lower()
        if "already exists" not in message:
            raise


def drop_customerban_table(apps, schema_editor):
    table_name = "appointments_customerban"
    if table_name not in schema_editor.connection.introspection.table_names():
        return
    CustomerBan = apps.get_model("appointments", "CustomerBan")
    schema_editor.delete_model(CustomerBan)


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0006_add_appointment_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="CustomerBan",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("start_date", models.DateField()),
                        ("end_date", models.DateField()),
                        ("reason", models.TextField(blank=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bans", to=settings.AUTH_USER_MODEL)),
                    ],
                )
            ],
            database_operations=[
                migrations.RunPython(create_customerban_table, drop_customerban_table),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="customerban",
                    index=models.Index(fields=["user", "end_date"], name="appointment_user_id_655365_idx"),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="CREATE INDEX IF NOT EXISTS appointment_user_id_655365_idx ON appointments_customerban (user_id, end_date);",
                    reverse_sql="DROP INDEX IF EXISTS appointment_user_id_655365_idx;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="appointment",
                    name="attended_at",
                    field=models.DateTimeField(blank=True, null=True),
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE appointments_appointment ADD COLUMN IF NOT EXISTS attended_at timestamp with time zone NULL;",
                    reverse_sql="ALTER TABLE appointments_appointment DROP COLUMN IF EXISTS attended_at;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="appointment",
                    name="is_attended",
                    field=models.BooleanField(blank=True, null=True),
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE appointments_appointment ADD COLUMN IF NOT EXISTS is_attended boolean NULL;",
                    reverse_sql="ALTER TABLE appointments_appointment DROP COLUMN IF EXISTS is_attended;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="appointment",
                    index=models.Index(fields=["staff", "start_datetime"], name="appointment_staff_i_b10e5e_idx"),
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="CREATE INDEX IF NOT EXISTS appointment_staff_i_b10e5e_idx ON appointments_appointment (staff_id, start_datetime);",
                    reverse_sql="DROP INDEX IF EXISTS appointment_staff_i_b10e5e_idx;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="appointment",
                    index=models.Index(fields=["shop", "start_datetime"], name="appointment_shop_id_f69843_idx"),
                )
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="CREATE INDEX IF NOT EXISTS appointment_shop_id_f69843_idx ON appointments_appointment (shop_id, start_datetime);",
                    reverse_sql="DROP INDEX IF EXISTS appointment_shop_id_f69843_idx;",
                ),
            ],
        ),
        migrations.RunSQL(
            sql="ALTER TABLE appointments_appointment DROP CONSTRAINT IF EXISTS exclude_overlap_per_staff_active;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=ExclusionConstraint(
                name="exclude_overlap_per_staff_active",
                expressions=[
                    (Func(F("start_datetime"), F("end_datetime"), function="tstzrange", output_field=DateTimeRangeField()), RangeOperators.OVERLAPS),
                    ("staff", RangeOperators.EQUAL),
                ],
                condition=Q(status__in=["pending", "confirmed", "suggested"]),
                index_type="GIST",
            ),
        ),
    ]
