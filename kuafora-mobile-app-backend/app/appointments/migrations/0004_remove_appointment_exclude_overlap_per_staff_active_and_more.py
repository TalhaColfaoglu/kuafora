from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    """
    Stub migration to align with production history.

    Asıl şema güncellemeleri 0005 migration'ında idempotent olarak yapılacak.
    """

    dependencies = [
        ("appointments", "0003_exclusion_constraints"),
    ]

    operations: list[migrations.operations.base.Operation] = []



