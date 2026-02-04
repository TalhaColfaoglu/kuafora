from django.db import migrations, models


def add_expires_at_if_missing(apps, schema_editor):
    """Add expires_at only if column does not exist (idempotent for existing DBs)."""
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'chat_chatban' AND column_name = 'expires_at'
        """)
        if cursor.fetchone():
            return
        cursor.execute(
            "ALTER TABLE chat_chatban ADD COLUMN expires_at timestamp with time zone NULL"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0004_chat_message_report_and_hidden"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="chatban",
                    name="expires_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_expires_at_if_missing, migrations.RunPython.noop),
            ],
        ),
    ]

