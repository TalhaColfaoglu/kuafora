from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0005_add_attendance_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='cancelled_by',
            field=models.CharField(blank=True, choices=[('customer', 'Customer'), ('staff', 'Staff'), ('system', 'System'), ('system_switch', 'System Switch')], default='system', max_length=20),
        ),
        migrations.AddField(
            model_name='appointment',
            name='payment_intent_id',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='appointment',
            name='payment_status',
            field=models.CharField(choices=[('none', 'None'), ('requires_action', 'Requires Action'), ('authorized', 'Authorized'), ('captured', 'Captured'), ('failed', 'Failed')], default='none', max_length=20),
        ),
        migrations.AddField(
            model_name='appointment',
            name='refund_status',
            field=models.CharField(choices=[('none', 'None'), ('queued', 'Queued'), ('processing', 'Processing'), ('refunded', 'Refunded'), ('failed', 'Failed')], default='none', max_length=20),
        ),
        migrations.AddField(
            model_name='appointment',
            name='rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='appointment',
            name='source',
            field=models.CharField(choices=[('partner', 'Partner'), ('mobile_customer', 'Mobile Customer')], default='partner', max_length=20),
        ),
    ]

