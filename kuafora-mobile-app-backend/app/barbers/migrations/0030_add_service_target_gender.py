# Hizmet cinsiyeti (unisex kuaför): target_gender = male / female / both

from django.db import migrations, models


def backfill_target_gender(apps, schema_editor):
    """Erkek/kadın kuaförlerde mevcut hizmetlere barbershop.gender ata; unisex'te null kalsın."""
    Service = apps.get_model("barbers", "Service")
    for svc in Service.objects.select_related("barbershop").iterator():
        shop_gender = getattr(svc.barbershop, "gender", None)
        if shop_gender == "male":
            svc.target_gender = "male"
            svc.save(update_fields=["target_gender"])
        elif shop_gender == "female":
            svc.target_gender = "female"
            svc.save(update_fields=["target_gender"])
        # unisex: leave null until partner edits


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0029_barbershop_service_duration_interval"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="target_gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "Erkek"), ("female", "Kadın"), ("both", "Kadın ve Erkek")],
                help_text="Unisex kuaförde: male/female/both. Erkek/kadın kuaförde otomatik.",
                max_length=10,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_target_gender, noop_reverse),
    ]
