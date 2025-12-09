# Generated manually to add missing fields to Review model

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0021_viewevent_device_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='dislikes',
            field=models.ManyToManyField(blank=True, related_name='disliked_reviews', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='review',
            name='likes',
            field=models.ManyToManyField(blank=True, related_name='liked_reviews', to=settings.AUTH_USER_MODEL),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'ALTER TABLE "barbers_review" '
                        'ADD COLUMN IF NOT EXISTS "replied_at" timestamp with time zone NULL;'
                    ),
                    reverse_sql=(
                        'ALTER TABLE "barbers_review" '
                        'DROP COLUMN IF EXISTS "replied_at";'
                    ),
                ),
            ],
            state_operations=[
        migrations.AddField(
            model_name='review',
            name='replied_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'ALTER TABLE "barbers_review" '
                        'ADD COLUMN IF NOT EXISTS "reply" text NULL;'
                    ),
                    reverse_sql=(
                        'ALTER TABLE "barbers_review" '
                        'DROP COLUMN IF EXISTS "reply";'
                    ),
                ),
            ],
            state_operations=[
        migrations.AddField(
            model_name='review',
            name='reply',
            field=models.TextField(blank=True, null=True),
                ),
            ],
        ),
    ]

