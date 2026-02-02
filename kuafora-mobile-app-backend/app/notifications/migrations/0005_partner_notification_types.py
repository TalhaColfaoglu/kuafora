# Generated migration: partner notification types (review, payment_reminder, staff_change, subscription_expiry, promo)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0004_rename_notificatio_user_id_7bdf7d_idx_notificatio_user_id_05b4bc_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("booking", "Randevu"),
                    ("chat", "Mesaj"),
                    ("reply", "Yorum Yanıtı"),
                    ("system", "Sistem"),
                    ("review", "Yeni Yorum"),
                    ("payment_reminder", "Ödeme Hatırlatması"),
                    ("staff_change", "Personel Değişikliği"),
                    ("subscription_expiry", "Abonelik Bitişi"),
                    ("promo", "Kampanya / Fırsat"),
                ],
                max_length=24,
            ),
        ),
    ]
