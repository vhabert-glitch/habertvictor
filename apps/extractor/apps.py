import os
import sys

from django.apps import AppConfig


class ExtractorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.extractor'
    verbose_name = 'Extraction de données'

    def ready(self):
        """Démarre le scheduler interne — désactivé par défaut.

        `ready()` est appelé dans TOUS les processus Django : chaque
        `manage.py ...` et chaque worker gunicorn. Sans garde explicite, le
        scheduler démarrait donc aussi pendant une migration ou un run de
        l'agent, et en autant d'exemplaires qu'il y a de workers en production
        — soit des scrapes en double sur les mêmes sources.

        La planification fiable se fait par cron (`scripts/update_data.sh`).
        Ce scheduler n'est là que pour un hébergement sans cron : il faut
        alors poser ENABLE_SCHEDULER=1 et un seul worker.
        """
        if os.environ.get('ENABLE_SCHEDULER', '').lower() not in ('1', 'true', 'yes'):
            return
        # avec runserver, ready() est appelé deux fois : on garde l'enfant
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return
        from apps.extractor.scheduler import start_scheduler
        start_scheduler()
