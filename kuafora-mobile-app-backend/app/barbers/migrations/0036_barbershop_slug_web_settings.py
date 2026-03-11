from django.db import migrations, models
from django.utils.text import slugify


def _barbershop_slugify(value: str) -> str:
    normalized = (value or "").strip().lower().translate(
        str.maketrans(
            {
                "ı": "i",
                "ğ": "g",
                "ü": "u",
                "ş": "s",
                "ö": "o",
                "ç": "c",
            }
        )
    )
    return slugify(normalized) or "salon"


def forwards(apps, schema_editor):
    Barbershop = apps.get_model("barbers", "Barbershop")
    BarbershopWebSettings = apps.get_model("barbers", "BarbershopWebSettings")

    for shop in Barbershop.objects.all().order_by("id"):
        if not shop.slug:
            base_slug = _barbershop_slugify(shop.name)
            candidate = base_slug
            suffix = 2
            while Barbershop.objects.filter(slug=candidate).exclude(pk=shop.pk).exists():
                suffix_text = f"-{suffix}"
                candidate = f"{base_slug[:220 - len(suffix_text)]}{suffix_text}"
                suffix += 1
            shop.slug = candidate
            shop.save(update_fields=["slug"])

        BarbershopWebSettings.objects.get_or_create(
            barbershop=shop,
            defaults={
                "theme_color": "forest",
                "heading_font": "cabinet",
                "body_font": "satoshi",
                "hero_style": "single_image",
                "services_style": "cards",
                "map_style": "embedded",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0035_service_optional_price_duration"),
    ]

    operations = [
        migrations.AddField(
            model_name="barbershop",
            name="slug",
            field=models.SlugField(blank=True, default=None, max_length=220, null=True, unique=True),
        ),
        migrations.CreateModel(
            name="BarbershopWebSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("theme_color", models.CharField(choices=[("forest", "Forest"), ("charcoal", "Charcoal"), ("sand", "Sand"), ("burgundy", "Burgundy"), ("midnight", "Midnight")], default="forest", max_length=20)),
                ("heading_font", models.CharField(choices=[("cabinet", "Cabinet Grotesk"), ("playfair", "Playfair Display"), ("manrope", "Manrope"), ("sora", "Sora")], default="cabinet", max_length=20)),
                ("body_font", models.CharField(choices=[("satoshi", "Satoshi"), ("inter", "Inter"), ("manrope", "Manrope"), ("dm_sans", "DM Sans")], default="satoshi", max_length=20)),
                ("hero_style", models.CharField(choices=[("single_image", "Büyük Tek Görsel"), ("gallery_slider", "Slayt / Galeri"), ("minimal", "Minimal")], default="single_image", max_length=24)),
                ("services_style", models.CharField(choices=[("list", "Liste"), ("cards", "Kartlar"), ("category_list", "Kategori Başlıklarıyla Liste")], default="cards", max_length=24)),
                ("map_style", models.CharField(choices=[("embedded", "MapTiler Gömülü Harita"), ("static", "Statik Harita + Link")], default="embedded", max_length=20)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("barbershop", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="web_settings", to="barbers.barbershop")),
            ],
            options={
                "verbose_name": "Salon web sayfası ayarı",
                "verbose_name_plural": "Salon web sayfası ayarları",
            },
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
