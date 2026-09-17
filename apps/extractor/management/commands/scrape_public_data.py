"""
Management command : scraping de données publiques complémentaires.

Sources :
  - France Compétences (RNCP/RS) : certifications & formations officielles
  - Pôle Emploi / France Travail ROME : fiches métiers & compétences
  - data.gouv.fr : datasets formations professionnelles
  - Mon Compte Formation : API publique formations IA
"""
import logging
import re
import time
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.extractor.models import JobPosting, FormationCatalog
from apps.extractor.classifier import (
    classify_training_type,
    classify_sector,
    compute_relevance_score,
    extract_skills,
)

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
}

# Requêtes IA pour les APIs publiques
AI_QUERIES = [
    'intelligence artificielle',
    'machine learning',
    'data scientist',
    'data engineer',
    'deep learning',
    'data analyst',
    'big data',
    'mlops',
    'cybersécurité',
    'cloud computing',
    'devops',
    'développeur python',
    'IA générative',
    'NLP traitement langage',
    'computer vision',
    'robotique',
    'automatisation',
    'blockchain',
    'IoT objets connectés',
]

# Codes ROME liés à l'IA / Data / Numérique
ROME_CODES_IA = [
    'M1805',  # Études et développement informatique
    'M1806',  # Conseil et maîtrise d'ouvrage en systèmes d'info
    'M1810',  # Production et exploitation de systèmes d'info
    'M1802',  # Expertise et support en systèmes d'info
    'M1803',  # Direction des systèmes d'info
    'M1804',  # Études et développement de réseaux de télécoms
    'M1801',  # Administration de systèmes d'info
    'M1807',  # Exploitation de systèmes de communication
    'M1808',  # Information géographique
    'M1809',  # Information météorologique
    'H1206',  # Management et ingénierie études, R&D
    'H1502',  # Management et ingénierie qualité industrielle
    'H2502',  # Management et ingénierie de maintenance industrielle
    'K2401',  # Recherche en sciences de l'homme et de la société
    'K2108',  # Enseignement supérieur
]


class Command(BaseCommand):
    help = 'Scrape données publiques : France Compétences, ROME, data.gouv.fr'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default='all',
            choices=['all', 'france_competences', 'rome', 'mcf', 'datagouv'],
            help='Source à scraper (default: all)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Nombre max de résultats par requête',
        )

    def handle(self, *args, **options):
        source = options['source']
        limit = options['limit']
        total = 0

        if source in ('all', 'france_competences'):
            self.stdout.write(self.style.NOTICE(
                '[Public] Scraping France Compétences (RNCP)...'
            ))
            count = self._scrape_france_competences(limit)
            total += count
            self.stdout.write(self.style.SUCCESS(
                f'  → {count} certifications importées'
            ))

        if source in ('all', 'rome'):
            self.stdout.write(self.style.NOTICE(
                '[Public] Scraping ROME / France Travail fiches métiers...'
            ))
            count = self._scrape_rome(limit)
            total += count
            self.stdout.write(self.style.SUCCESS(
                f'  → {count} fiches métiers importées'
            ))

        if source in ('all', 'mcf'):
            self.stdout.write(self.style.NOTICE(
                '[Public] Scraping Mon Compte Formation...'
            ))
            count = self._scrape_mcf(limit)
            total += count
            self.stdout.write(self.style.SUCCESS(
                f'  → {count} formations importées'
            ))

        if source in ('all', 'datagouv'):
            self.stdout.write(self.style.NOTICE(
                '[Public] Scraping data.gouv.fr formations IA...'
            ))
            count = self._scrape_datagouv(limit)
            total += count
            self.stdout.write(self.style.SUCCESS(
                f'  → {count} éléments importés'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'\n[Public] Total : {total} éléments importés'
        ))

    # ─── France Compétences RNCP ──────────────────────────────────────

    def _scrape_france_competences(self, limit):
        """Scrape les certifications RNCP liées à l'IA depuis France Compétences."""
        count = 0
        api_url = 'https://www.francecompetences.fr/recherche/rncp/'

        for query in AI_QUERIES[:10]:
            try:
                search_url = f'{api_url}?search={quote_plus(query)}'
                resp = requests.get(search_url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find certification entries
                entries = soup.find_all(
                    ['div', 'a', 'article'],
                    class_=re.compile(r'result|card|certification|fiche', re.IGNORECASE),
                )

                for entry in entries[:limit]:
                    title_el = entry.find(['h2', 'h3', 'h4', 'a', 'span'])
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue

                    # Get URL
                    link = entry.find('a', href=True)
                    cert_url = ''
                    if link:
                        href = link.get('href', '')
                        cert_url = urljoin('https://www.francecompetences.fr', href)

                    # Get extra info
                    extra = entry.get_text(' ', strip=True)

                    # Determine provider from text
                    provider = 'France Compétences (RNCP)'
                    provider_el = entry.find(
                        string=re.compile(r'(organisme|certificateur)', re.IGNORECASE)
                    )
                    if provider_el:
                        parent = provider_el.find_parent()
                        if parent:
                            provider = parent.get_text(strip=True)[:300]

                    full_text = f'{title} {extra}'

                    _, created = FormationCatalog.objects.update_or_create(
                        name=title[:500],
                        provider=provider[:300],
                        defaults={
                            'description': extra[:2000],
                            'sector': classify_sector(full_text),
                            'training_type': 'certification',
                            'url': cert_url,
                            'skills_covered': extract_skills(full_text),
                        },
                    )
                    if created:
                        count += 1

                time.sleep(1.0)

            except Exception as e:
                logger.warning(f'France Compétences "{query}": {e}')

        return count

    # ─── ROME / France Travail fiches métiers ─────────────────────────

    def _scrape_rome(self, limit):
        """Scrape les fiches métiers ROME depuis l'API France Travail."""
        count = 0

        # API publique France Travail - ROME
        rome_api = 'https://api.francetravail.io/partenaire/rome/v1/metier/appellation'
        rome_fiche_api = 'https://api.francetravail.io/partenaire/rome/v1/metier'

        # Fallback: scrape le site web
        for rome_code in ROME_CODES_IA:
            try:
                # Try direct fiche URL
                url = f'https://candidat.francetravail.fr/marche-du-travail/fichemetierrome?codeRome={rome_code}'
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                # Extract job title
                title_el = soup.find('h1') or soup.find('h2')
                title = title_el.get_text(strip=True) if title_el else ''
                if not title:
                    title = f'Métier ROME {rome_code}'

                # Extract description / competences
                desc_parts = []
                for section in soup.find_all(['section', 'div', 'article']):
                    heading = section.find(['h2', 'h3', 'h4'])
                    if heading:
                        heading_text = heading.get_text(strip=True).lower()
                        if any(kw in heading_text for kw in [
                            'compétence', 'activité', 'savoir', 'accès',
                            'description', 'définition',
                        ]):
                            text = section.get_text(' ', strip=True)
                            if len(text) > 20:
                                desc_parts.append(text[:500])

                description = '\n'.join(desc_parts)
                if not description:
                    description = soup.get_text(' ', strip=True)[:2000]

                full_text = f'{title} {description} {rome_code}'

                # Save as JobPosting (enriches demand data)
                _, created = JobPosting.objects.update_or_create(
                    url=url,
                    defaults={
                        'title': f'{title} ({rome_code})'[:500],
                        'company': 'France Travail (ROME)',
                        'source': 'rome',
                        'sector': classify_sector(full_text),
                        'skills': extract_skills(full_text),
                        'location': 'France',
                        'training_type_match': classify_training_type(full_text),
                        'raw_description': description[:5000],
                        'relevance_score': compute_relevance_score(full_text),
                    },
                )
                if created:
                    count += 1

                time.sleep(0.5)

            except Exception as e:
                logger.warning(f'ROME {rome_code}: {e}')

        return count

    # ─── Mon Compte Formation ─────────────────────────────────────────

    def _scrape_mcf(self, limit):
        """Scrape Mon Compte Formation API pour les formations IA."""
        count = 0
        api_base = 'https://api-cpf.moncompteformation.gouv.fr/api/public/v1/formations'

        for query in AI_QUERIES[:12]:
            try:
                params = {
                    'q': query,
                    'page': 1,
                    'per_page': min(limit, 20),
                }
                resp = requests.get(
                    api_base,
                    params=params,
                    headers={**HEADERS, 'Accept': 'application/json'},
                    timeout=15,
                )
                if resp.status_code != 200:
                    # Try alternative endpoint
                    alt_url = f'https://www.moncompteformation.gouv.fr/espace-prive/html/#/recherche?q={quote_plus(query)}'
                    resp2 = requests.get(alt_url, headers=HEADERS, timeout=15)
                    if resp2.status_code == 200:
                        count += self._parse_mcf_html(resp2.text, query)
                    continue

                data = resp.json()
                formations = data if isinstance(data, list) else data.get('results', data.get('formations', []))

                for f in formations[:limit]:
                    name = f.get('intitule', f.get('titre', f.get('title', '')))
                    if not name:
                        continue

                    provider = f.get('organisme', f.get('provider', ''))
                    if isinstance(provider, dict):
                        provider = provider.get('nom', provider.get('name', ''))

                    description = f.get('description', f.get('objectif', ''))
                    price = f.get('prix', f.get('price', ''))
                    if isinstance(price, (int, float)):
                        price = f'{price} €'
                    duration = f.get('duree', f.get('duration', ''))
                    url = f.get('url', f.get('lien', ''))

                    full_text = f'{name} {description} {provider}'

                    _, created = FormationCatalog.objects.update_or_create(
                        name=name[:500],
                        provider=provider[:300] if provider else 'Mon Compte Formation',
                        defaults={
                            'description': str(description)[:2000],
                            'sector': classify_sector(full_text),
                            'training_type': 'certification',
                            'url': str(url)[:1000],
                            'price': str(price)[:100],
                            'duration': str(duration)[:100],
                            'skills_covered': extract_skills(full_text),
                        },
                    )
                    if created:
                        count += 1

                time.sleep(0.8)

            except Exception as e:
                logger.warning(f'MCF "{query}": {e}')

        return count

    def _parse_mcf_html(self, html, query):
        """Parse HTML de Mon Compte Formation si l'API n'est pas dispo."""
        count = 0
        try:
            soup = BeautifulSoup(html, 'html.parser')
            cards = soup.find_all(
                ['div', 'article'],
                class_=re.compile(r'card|formation|result', re.IGNORECASE),
            )
            for card in cards[:20]:
                title_el = card.find(['h2', 'h3', 'h4', 'a'])
                if not title_el:
                    continue
                name = title_el.get_text(strip=True)
                if not name or len(name) < 10:
                    continue

                desc = card.get_text(' ', strip=True)
                full_text = f'{name} {desc}'

                _, created = FormationCatalog.objects.update_or_create(
                    name=name[:500],
                    provider='Mon Compte Formation',
                    defaults={
                        'description': desc[:2000],
                        'sector': classify_sector(full_text),
                        'training_type': 'certification',
                        'skills_covered': extract_skills(full_text),
                    },
                )
                if created:
                    count += 1
        except Exception as e:
            logger.warning(f'MCF HTML parse: {e}')

        return count

    # ─── data.gouv.fr ─────────────────────────────────────────────────

    def _scrape_datagouv(self, limit):
        """Scrape les datasets data.gouv.fr liés aux formations IA."""
        count = 0
        api_url = 'https://www.data.gouv.fr/api/1/datasets/'

        queries = [
            'formation intelligence artificielle',
            'formation numérique compétences',
            'emploi data scientist',
            'métiers numérique',
            'certification professionnelle',
        ]

        for query in queries:
            try:
                params = {
                    'q': query,
                    'page_size': min(limit, 10),
                }
                resp = requests.get(api_url, params=params, timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                datasets = data.get('data', [])

                for ds in datasets:
                    title = ds.get('title', '')
                    description = ds.get('description', '')
                    ds_url = ds.get('page', ds.get('uri', ''))
                    org = ds.get('organization', {})
                    org_name = org.get('name', 'data.gouv.fr') if org else 'data.gouv.fr'

                    if not title:
                        continue

                    full_text = f'{title} {description}'

                    # Check relevance to IA/formation
                    if compute_relevance_score(full_text) < 0.2:
                        continue

                    # Check for downloadable resources (CSV/JSON)
                    resources = ds.get('resources', [])
                    for resource in resources[:3]:
                        res_format = resource.get('format', '').lower()
                        if res_format in ('csv', 'json', 'xlsx', 'xls'):
                            res_url = resource.get('url', '')
                            res_title = resource.get('title', title)

                            _, created = FormationCatalog.objects.update_or_create(
                                name=f'{res_title[:450]} (data.gouv)',
                                provider=org_name[:300],
                                defaults={
                                    'description': description[:2000],
                                    'sector': classify_sector(full_text),
                                    'url': res_url[:1000] or ds_url[:1000],
                                    'skills_covered': extract_skills(full_text),
                                },
                            )
                            if created:
                                count += 1

                time.sleep(0.5)

            except Exception as e:
                logger.warning(f'data.gouv "{query}": {e}')

        return count
