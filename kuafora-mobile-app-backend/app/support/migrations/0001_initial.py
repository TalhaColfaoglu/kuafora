from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # DB side: make it idempotent and handle leftover PostgreSQL row type conflicts.
            database_operations=[
                migrations.RunSQL(
                    sql=r"""
                    DO $$
                    BEGIN
                      -- If the table does not exist but the row type exists (leftover from a previous attempt),
                      -- CREATE TABLE will fail with: pg_type_typname_nsp_index.
                      IF to_regclass('public.support_supportrequest') IS NULL THEN
                        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'support_supportrequest' AND typnamespace = 2200) THEN
                          DROP TYPE public.support_supportrequest CASCADE;
                        END IF;

                        CREATE TABLE IF NOT EXISTS public.support_supportrequest (
                          id bigserial PRIMARY KEY,
                          user_id uuid NULL REFERENCES public.users_user(id) ON DELETE SET NULL,
                          email varchar(254) NOT NULL DEFAULT '',
                          phone varchar(32) NOT NULL DEFAULT '',
                          type varchar(20) NOT NULL DEFAULT 'support',
                          message text NOT NULL,
                          status varchar(20) NOT NULL DEFAULT 'new',
                          admin_note text NOT NULL DEFAULT '',
                          app_version varchar(64) NOT NULL DEFAULT '',
                          platform varchar(32) NOT NULL DEFAULT '',
                          device_info varchar(255) NOT NULL DEFAULT '',
                          user_agent text NOT NULL DEFAULT '',
                          ip_address inet NULL,
                          created_at timestamptz NOT NULL DEFAULT now(),
                          updated_at timestamptz NOT NULL DEFAULT now()
                        );
                      END IF;
                    END $$;
                    """,
                    reverse_sql=r"""
                    DROP TABLE IF EXISTS public.support_supportrequest;
                    """,
                ),
            ],
            # Django state: keep model definition as usual.
            state_operations=[
                migrations.CreateModel(
                    name="SupportRequest",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("email", models.EmailField(blank=True, default="", max_length=254)),
                        ("phone", models.CharField(blank=True, default="", max_length=32)),
                        (
                            "type",
                            models.CharField(
                                choices=[("support", "Destek"), ("suggestion", "Öneri"), ("complaint", "Şikayet")],
                                default="support",
                                max_length=20,
                            ),
                        ),
                        ("message", models.TextField()),
                        (
                            "status",
                            models.CharField(
                                choices=[("new", "Yeni"), ("in_progress", "İşleme Alındı"), ("resolved", "Çözüldü")],
                                default="new",
                                max_length=20,
                            ),
                        ),
                        ("admin_note", models.TextField(blank=True, default="")),
                        ("app_version", models.CharField(blank=True, default="", max_length=64)),
                        ("platform", models.CharField(blank=True, default="", max_length=32)),
                        ("device_info", models.CharField(blank=True, default="", max_length=255)),
                        ("user_agent", models.TextField(blank=True, default="")),
                        ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "user",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="support_requests",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Destek Talebi",
                        "verbose_name_plural": "Destek Talepleri",
                        "ordering": ("-created_at",),
                    },
                ),
            ],
        )
    ]


