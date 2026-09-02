import os
from django.apps import AppConfig


class ExtractorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.extractor'
    verbose_name = 'Extraction de données'

    def ready(self):
        # Éviter le double démarrage avec le reloader de Django
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_DEV'):
            from apps.extractor.scheduler import start_scheduler
            start_scheduler()
