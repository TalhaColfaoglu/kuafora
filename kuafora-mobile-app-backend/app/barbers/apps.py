from django.apps import AppConfig


class BarbersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.barbers"

    def ready(self):
        from . import signals  # noqa: F401

