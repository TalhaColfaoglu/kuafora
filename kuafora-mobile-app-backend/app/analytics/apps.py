from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.analytics'
    verbose_name = 'Analytics & Tracking'
    
    def ready(self):
        # Register signals
        import app.analytics.signals

