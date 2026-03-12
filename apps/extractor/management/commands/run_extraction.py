"""
Management command : lance tous les extracteurs en séquence.
Usage : python manage.py run_extraction [--only jobs,news,communities,social,trends]
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


EXTRACTORS = {
    'jobs': {
        'label': 'Offres d\'emploi (Indeed, APEC, WTTJ, France Travail, Adzuna, HelloWork)',
        'command': 'scrape_jobs',
        'args': ['--source', 'all'],
    },
    'news': {
        'label': 'Actualités & flux RSS (30+ sources)',
        'command': 'scrape_news',
        'args': [],
    },
    'communities': {
        'label': 'Communautés (Reddit, Hacker News, Stack Overflow)',
        'command': 'scrape_communities',
        'args': ['--source', 'all'],
    },
    'social': {
        'label': 'Signaux sociaux (LinkedIn, X/Twitter)',
        'command': 'scrape_social',
        'args': [],
    },
    'trends': {
        'label': 'Tendances (GitHub Trending, PyPI stats)',
        'command': 'scrape_trends',
        'args': ['--source', 'all'],
    },
}


class Command(BaseCommand):
    help = 'Lance tous les extracteurs de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only', type=str, default='',
            help='Extracteurs à lancer (séparés par virgules). '
                 f'Options : {", ".join(EXTRACTORS.keys())}'
        )

    def handle(self, *args, **options):
        only = options['only']
        if only:
            selected = [s.strip() for s in only.split(',')]
        else:
            selected = list(EXTRACTORS.keys())

        self.stdout.write(self.style.NOTICE(
            f'\n{"="*60}\n'
            f'  IA FORMATION RADAR — Extraction de données\n'
            f'  Sources sélectionnées : {", ".join(selected)}\n'
            f'{"="*60}\n'
        ))

        for key in selected:
            if key not in EXTRACTORS:
                self.stdout.write(self.style.ERROR(f'Source inconnue : {key}'))
                continue

            ext = EXTRACTORS[key]
            self.stdout.write(self.style.NOTICE(f'\n=== {ext["label"]} ==='))
            try:
                call_command(ext['command'], *ext['args'])
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erreur {key}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'  Extraction terminée.\n'
            f'{"="*60}'
        ))
