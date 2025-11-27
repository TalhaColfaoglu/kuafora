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
        # 1. CustomerBan tablosunu oluştur
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
        ),
        # 2. CustomerBan için indeks ekle (yeni isimle)
        migrations.AddIndex(
            model_name='customerban',
            index=models.Index(fields=['user', 'end_date'], name='appointment_user_id_655365_idx'),
        ),
        
        # 3. Appointment tablosuna attended alanlarını ekle (0008'de görünüyordu)
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

        # 4. Appointment tablosuna indeksleri ekle (yeni isimleriyle, Rename kullanmadan)
        # Eğer eski isimli indeksler varsa bile bunlar yeni isimlerle eklenir.
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['staff', 'start_datetime'], name='appointment_staff_i_b10e5e_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['shop', 'start_datetime'], name='appointment_shop_id_f69843_idx'),
        ),

        # 5. Constraint işlemleri (önce varsa silmeyi dene - SQL ile, sonra ekle)
        # Güvenli silme işlemi (raw SQL)
        migrations.RunSQL(
            sql="ALTER TABLE appointments_appointment DROP CONSTRAINT IF EXISTS exclude_overlap_per_staff_active;",
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Constraint'i yeniden oluştur
        migrations.AddConstraint(
            model_name='appointment',
            constraint=ExclusionConstraint(
                condition=models.Q(('status__in', ['pending', 'confirmed', 'suggested'])),
                expressions=[(Func(F('start_datetime'), F('end_datetime'), function='tstzrange', output_field=DateTimeRangeField()), RangeOperators.OVERLAPS), ('staff', RangeOperators.EQUAL)],
                index_type='GIST',
                name='exclude_overlap_per_staff_active'
            ),
        ),
    ]
