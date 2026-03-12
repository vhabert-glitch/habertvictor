"""
Management command : collecte des données de tendances.
Sources : GitHub Trending, Google Trends (via scraping), PyPI stats.
"""
import logging
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.extractor.models import TrendData
from apps.extractor.classifier import compute_relevance_score

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# Termes à suivre sur Google Trends
GOOGLE_TRENDS_TERMS = [
    'formation intelligence artificielle',
    'formation machine learning',
    'formation data science',
    'certification IA',
    'prompt engineering formation',
    'LLM formation',
    'AI Act conformité',
    'MLOps formation',
    'deep learning cours',
    'compétences IA',
]

# Packages Python IA à suivre sur PyPI
PYPI_PACKAGES = [
    'tensorflow', 'torch', 'transformers', 'scikit-learn',
    'langchain', 'openai', 'anthropic', 'huggingface-hub',
    'mlflow', 'ray', 'fastapi', 'streamlit',
    'pandas', 'numpy', 'matplotlib', 'seaborn',
    'spacy', 'nltk', 'opencv-python', 'ultralytics',
]


class Command(BaseCommand):
    help = 'Collecte les données de tendances (GitHub, Google Trends, PyPI)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source', type=str, default='all',
            help='Source : github, pypi, all'
        )

    def handle(self, *args, **options):
        source = options['source']
        total = 0

        if source in ('github', 'all'):
            self.stdout.write(self.style.NOTICE('\n--- GITHUB TRENDING ---'))
            total += self._scrape_github_trending()

        if source in ('pypi', 'all'):
            self.stdout.write(self.style.NOTICE('\n--- PYPI STATS ---'))
            total += self._scrape_pypi_stats()

        self.stdout.write(self.style.SUCCESS(f'\nTotal : {total} données de tendances collectées.'))

    # ─── GITHUB TRENDING ─────────────────────────────────────────────────

    def _scrape_github_trending(self):
        """Scrape GitHub Trending pour les repos IA/ML."""
        count = 0
        languages = ['python', '']  # Python + tous langages
        periods = ['daily', 'weekly']

        for lang in languages:
            for period in periods:
                try:
                    url = f"https://github.com/trending/{lang}?since={period}"
                    resp = requests.get(url, headers=HEADERS, timeout=15)
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, 'html.parser')
                    repos = soup.select('article.Box-row, [class*="Box-row"]')

                    for repo in repos:
                        # Nom du repo
                        name_el = repo.select_one('h2 a, h1 a')
                        if not name_el:
                            continue
                        repo_name = name_el.get_text(strip=True).replace('\n', '').replace(' ', '')

                        # Description
                        desc_el = repo.select_one('p')
                        description = desc_el.get_text(strip=True) if desc_el else ''

                        full_text = f"{repo_name} {description}"

                        # Filtrer : garder seulement les repos liés à l'IA
                        ai_keywords = [
                            'ai', 'ml', 'machine learning', 'deep learning',
                            'neural', 'nlp', 'llm', 'gpt', 'transformer',
                            'diffusion', 'computer vision', 'data science',
                            'reinforcement learning', 'rag', 'agent',
                        ]
                        if not any(kw in full_text.lower() for kw in ai_keywords):
                            continue

                        # Stars aujourd'hui
                        stars_el = repo.select_one('[class*="float-sm-right"], .d-inline-block.float-sm-right')
                        stars_today = 0
                        if stars_el:
                            stars_text = stars_el.get_text(strip=True)
                            nums = re.findall(r'[\d,]+', stars_text)
                            if nums:
                                stars_today = int(nums[0].replace(',', ''))

                        # Total stars
                        total_stars = 0
                        star_links = repo.select('a[href*="/stargazers"]')
                        for sl in star_links:
                            st = sl.get_text(strip=True).replace(',', '')
                            if st.isdigit():
                                total_stars = int(st)
                                break

                        repo_url = f"https://github.com/{repo_name}"

                        TrendData.objects.update_or_create(
                            source='github',
                            keyword=repo_name,
                            measured_at=timezone.now(),
                            defaults={
                                'value': stars_today,
                                'region': 'global',
                                'category': f"{lang or 'all'}/{period}",
                                'metadata': {
                                    'description': description[:500],
                                    'total_stars': total_stars,
                                    'url': repo_url,
                                    'language': lang or 'all',
                                    'period': period,
                                },
                            }
                        )
                        count += 1

                    self.stdout.write(
                        f"  GitHub trending {lang or 'all'}/{period}: "
                        f"{len(repos)} repos analysés"
                    )
                except Exception as e:
                    logger.error(f"GitHub trending {lang}/{period}: {e}")

        return count

    # ─── PYPI STATS ──────────────────────────────────────────────────────

    def _scrape_pypi_stats(self):
        """Collecte les stats de téléchargement des packages IA Python via PyPI API."""
        count = 0
        now = timezone.now()

        for package in PYPI_PACKAGES:
            try:
                # PyPI JSON API
                url = f"https://pypi.org/pypi/{package}/json"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                info = data.get('info', {})
                version = info.get('version', '')
                summary = info.get('summary', '')
                home_page = info.get('home_page', info.get('project_url', ''))

                # Nombre de releases comme proxy d'activité
                releases = data.get('releases', {})
                num_releases = len(releases)

                # Dernière release
                last_release_date = None
                if version in releases and releases[version]:
                    upload_time = releases[version][0].get('upload_time')
                    if upload_time:
                        last_release_date = upload_time

                TrendData.objects.update_or_create(
                    source='pypi',
                    keyword=package,
                    measured_at=now,
                    defaults={
                        'value': num_releases,
                        'region': 'global',
                        'category': 'python-ai-packages',
                        'metadata': {
                            'version': version,
                            'summary': summary[:300],
                            'home_page': home_page,
                            'last_release': last_release_date,
                            'num_releases': num_releases,
                        },
                    }
                )
                count += 1
                self.stdout.write(f"  PyPI {package}: v{version} ({num_releases} releases)")

            except Exception as e:
                logger.error(f"PyPI {package}: {e}")

        return count
