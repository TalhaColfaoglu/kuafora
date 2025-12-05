from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db.models import F, Func, Q

class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0006_add_appointment_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
                migrations.CreateModel(
            name='CustomerBan',
                    fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bans', to=settings.AUTH_USER_MODEL)),
                    ],
            options={
                'indexes': [
                    models.Index(fields=['user', 'end_date'], name='appointments_cust_user_id_idx'),
            ],
            },
        ),
                migrations.AddField(
            model_name='appointment',
            name='attended_at',
                    field=models.DateTimeField(blank=True, null=True),
        ),
                migrations.AddField(
            model_name='appointment',
            name='is_attended',
                    field=models.BooleanField(blank=True, null=True),
        ),
        # Exclusion constraint güncellemesi
        migrations.RunSQL(
            sql="ALTER TABLE appointments_appointment DROP CONSTRAINT IF EXISTS exclude_overlap_per_staff_active;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddConstraint(
            model_name='appointment',
            constraint=ExclusionConstraint(
                name='exclude_overlap_per_staff_active',
                expressions=[
                    (Func(F('start_datetime'), F('end_datetime'), function='tstzrange', output_field=DateTimeRangeField()), RangeOperators.OVERLAPS),
                    ('staff', RangeOperators.EQUAL),
                ],
                condition=Q(status__in=['pending', 'confirmed', 'suggested']),
                index_type='GIST',
            ),
        ),
    ]
