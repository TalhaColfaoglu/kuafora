# Generated manually: Ömür boyu kuponları kaldır — mevcut lifetime kuponları pasif yap

from django.db import migrations


def deactivate_lifetime_coupons(apps, schema_editor):
    Coupon = apps.get_model("subscriptions", "Coupon")
    Coupon.objects.filter(discount_type="lifetime").update(is_active=False)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0002_initial_data"),
    ]

    operations = [
        migrations.RunPython(deactivate_lifetime_coupons, noop),
    ]
