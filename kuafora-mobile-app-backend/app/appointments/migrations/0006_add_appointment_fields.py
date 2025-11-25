from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0005_add_attendance_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='appointment',
                    name='cancelled_by',
                    field=models.CharField(blank=True, choices=[('customer', 'Customer'), ('staff', 'Staff'), ('system', 'System'), ('system_switch', 'System Switch')], default='system', max_length=20),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE appointments_appointment "
                        "ADD COLUMN IF NOT EXISTS cancelled_by varchar(20) "
                        "DEFAULT 'system'::varchar NOT NULL;"
                    ),
                    reverse_sql="ALTER TABLE appointments_appointment DROP COLUMN IF EXISTS cancelled_by;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='appointment',
                    name='payment_intent_id',
                    field=models.CharField(blank=True, max_length=120, null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE appointments_appointment "
                        "ADD COLUMN IF NOT EXISTS payment_intent_id varchar(120);"
                    ),
                    reverse_sql="ALTER TABLE appointments_appointment DROP COLUMN IF EXISTS payment_intent_id;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='appointment',
                    name='payment_status',
                    field=models.CharField(choices=[('none', 'None'), ('requires_action', 'Requires Action'), ('authorized', 'Authorized'), ('captured', 'Captured'), ('failed', 'Failed')], default='none', max_length=20),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE appointments_appointment "
                        "ADD COLUMN IF NOT EXISTS payment_status varchar(20) "
                        "DEFAULT 'none'::varchar NOT NULL;"
                    ),
                    reverse_sql="ALTER TABLE appointments_appointment DROP COLUMN IF EXISTS payment_status;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='appointment',
                    name='refund_status',
                    field=models.CharField(choices=[('none', 'None'), ('queued', 'Queued'), ('processing', 'Processing'), ('refunded', 'Refunded'), ('failed', 'Failed')], default='none', max_length=20),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE appointments_appointment "
                        "ADD COLUMN IF NOT EXISTS refund_status varchar(20) "
                        "DEFAULT 'none'::varchar NOT NULL;"
                    ),
                    reverse_sql="ALTER TABLE appointments_appointment DROP COLUMN IF EXISTS refund_status;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='appointment',
                    name='rejection_reason',
                    field=models.TextField(blank=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE appointments_appointment "
                        "ADD COLUMN IF NOT EXISTS rejection_reason text "
                        "DEFAULT ''::text NOT NULL;"
                    ),
                    reverse_sql="ALTER TABLE appointments_appointment DROP COLUMN IF EXISTS rejection_reason;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='appointment',
                    name='source',
                    field=models.CharField(choices=[('partner', 'Partner'), ('mobile_customer', 'Mobile Customer')], default='partner', max_length=20),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE appointments_appointment "
                        "ADD COLUMN IF NOT EXISTS source varchar(20) "
                        "DEFAULT 'partner'::varchar NOT NULL;"
                    ),
                    reverse_sql="ALTER TABLE appointments_appointment DROP COLUMN IF EXISTS source;",
                ),
            ],
        ),
    ]

