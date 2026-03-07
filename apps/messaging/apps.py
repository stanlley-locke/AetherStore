from django.apps import AppConfig


class MessagingConfig(AppConfig):
    name = 'apps.messaging'
    verbose_name = 'AetherStore Messaging'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        import apps.messaging.signals  # noqa
