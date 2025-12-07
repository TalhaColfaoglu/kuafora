from django.db import migrations


class Migration(migrations.Migration):
    """
    Safety migration to fix previous LastViewed unique_together issues.

    Eski bir migration, users_lastviewed tablosundaki (user_id, barbershop_id)
    constraint'ini silmeye çalışırken, veritabanında bu constraint olmadığı için
    "Found wrong number (0) of constraints..." hatası veriyordu.

    0004 ve 0005 zaten LastViewed ile ilgili tabloyu/ilişkileri temizliyor.
    Bu 0006 migration'ı bilinçli olarak BOŞ bırakıyoruz ki,
    üretim ortamında migrate sırasında hiçbir şey yapmadan sorunsuz geçilsin.
    """

    dependencies = [
        ("users", "0005_cleanup_old_tables"),
    ]

    operations = [
        # Bilinçli olarak no-op. Veritabanı mevcut haline dokunmuyoruz.
    ]


