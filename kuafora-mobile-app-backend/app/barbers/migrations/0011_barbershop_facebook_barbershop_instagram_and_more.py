from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    """
    Stub migration to match production history.

    Gerçek şema değişiklikleri 0012 migration'ında idempotent olarak
    (IF NOT EXISTS ile) uygulanacak. Bu dosya yalnızca
    'barbers.0011_barbershop_facebook_barbershop_instagram_and_more'
    migration'ının disk üzerinde bulunmasını sağlar.
    """

    dependencies = [
        ("barbers", "0010_calendarauditlog_messageviewlog_officialholiday_and_more"),
    ]

    operations: list[migrations.operations.base.Operation] = []



