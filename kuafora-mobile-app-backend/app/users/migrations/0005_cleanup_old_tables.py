from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_alter_lastviewed_unique_together_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DROP TABLE IF EXISTS users_lastviewed CASCADE;
            DROP TABLE IF EXISTS users_favorite CASCADE;
            """,
            reverse_sql=""
        ),
    ]
