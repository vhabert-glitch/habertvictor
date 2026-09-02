"""
Management command : scraping des offres d'emploi IA depuis multiples sources.
Sources : Adzuna, APEC, Indeed, Welcome to the Jungle, France Travail, HelloWork, Talent.io
"""
import logging
import os
import re
import json
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from apps.extractor.models import JobPosting
from apps.extractor.classifier import (
    classify_training_type, classify_sector,
    compute_relevance_score, extract_skills,
)

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
}

SEARCH_QUERIES = [
    # ── IA core ──
    'intelligence artificielle',
    'machine learning',
    'data scientist',
    'NLP deep learning',
    'MLOps',
    'IA générative LLM',
    'ingénieur IA',
    'data engineer',
    'computer vision',
    'prompt engineer',
    # ── Innovation & rôles hybrides IA ──
    'directeur innovation intelligence artificielle',
    'responsable innovation digitale',
    'chief digital officer',
    'chief data officer',
    'transformation digitale IA',
    'innovation manager data',
    'responsable R&D intelligence artificielle',
    'head of AI',
    'VP innovation',
    'digital transformation officer',
    # ── Cybersécurité ──
    'cybersécurité IA',
    'cyberdéfense intelligence artificielle',
    'analyste SOC IA',
    'threat intelligence machine learning',
    # ── Énergie ──
    'nucléaire intelligence artificielle',
    'énergie machine learning',
    'maintenance prédictive énergie',
    'smart grid IA',
    'data scientist énergie nucléaire',
    # ── Santé ──
    'IA santé',
    'machine learning santé médical',
    'data scientist pharma',
    'imagerie médicale intelligence artificielle',
    'NLP santé dossier médical',
    # ── Industrie ──
    'IA industrie manufacturing',
    'robotique intelligence artificielle',
    'maintenance prédictive usine',
    'digital twin jumeau numérique',
    'supply chain machine learning',
    # ── Rôles émergents IA ──
    'chief ai officer',
    'ai product manager',
    'ai ethics officer',
    'context engineer',
    'ai solution architect',
    'ai reliability engineer',
    'ingénieur RAG retrieval augmented generation',
    'responsable IA générative',
    'AI governance manager',
    'prompt engineer senior',
    'AI agents developer',
    'vector database engineer',
]


class Command(BaseCommand):
    help = 'Scrape les offres d\'emploi IA depuis toutes les sources configurées'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source', type=str, default='all',
            help='Source : adzuna, apec, indeed, wttj, francetravail, hellowork, all'
        )
        parser.add_argument('--limit', type=int, default=30, help='Résultats max par requête')

    def handle(self, *args, **options):
        source = options['source']
        limit = options['limit']
        total = 0

        scrapers = {
            'adzuna': self._scrape_adzuna,
            'apec': self._scrape_apec,
            'indeed': self._scrape_indeed,
            'wttj': self._scrape_wttj,
            'francetravail': self._scrape_france_travail,
            'hellowork': self._scrape_hellowork,
            'linkedin': self._scrape_linkedin,
        }

        if source == 'all':
            for name, scraper in scrapers.items():
                self.stdout.write(self.style.NOTICE(f'\n--- {name.upper()} ---'))
                total += scraper(limit)
        elif source in scrapers:
            total = scrapers[source](limit)
        else:
            self.stdout.write(self.style.ERROR(f'Source inconnue: {source}'))
            return

        if total == 0:
            self._generate_sample_jobs()

        self.stdout.write(self.style.SUCCESS(f'\nTotal : {total} offres traitées.'))

    def _save_job(self, title, source, url, description='', location=''):
        """Sauvegarde une offre avec classification automatique."""
        full_text = f"{title} {description}"
        try:
            _, created = JobPosting.objects.update_or_create(
                url=url if url else f"no-url-{source}-{title[:50]}",
                defaults={
                    'title': title[:500],
                    'source': source,
                    'sector': classify_sector(full_text),
                    'skills': extract_skills(full_text),
                    'location': location[:255] if location else '',
                    'training_type_match': classify_training_type(full_text),
                    'raw_description': description[:2000],
                    'relevance_score': compute_relevance_score(full_text),
                }
            )
            return 1 if created else 0
        except Exception as e:
            logger.error(f"Erreur sauvegarde {source}: {e}")
            return 0

    # ─── ADZUNA (API gratuite) ───────────────────────────────────────────

    def _scrape_adzuna(self, limit):
        app_id = os.getenv('ADZUNA_APP_ID', '')
        app_key = os.getenv('ADZUNA_APP_KEY', '')
        if not app_id or not app_key:
            self.stdout.write(self.style.WARNING('  ADZUNA_APP_ID/KEY non configurés, skip.'))
            return 0

        count = 0
        for query in SEARCH_QUERIES[:12]:
            try:
                url = (
                    f"https://api.adzuna.com/v1/api/jobs/fr/search/1"
                    f"?app_id={app_id}&app_key={app_key}"
                    f"&results_per_page={limit}&what={quote_plus(query)}"
                )
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                for r in resp.json().get('results', []):
                    count += self._save_job(
                        r.get('title', ''), 'Adzuna',
                        r.get('redirect_url', ''),
                        r.get('description', ''),
                        r.get('location', {}).get('display_name', '')
                    )
                self.stdout.write(f"  Adzuna '{query}': OK")
            except Exception as e:
                logger.error(f"Adzuna '{query}': {e}")
        return count

    # ─── APEC ────────────────────────────────────────────────────────────

    def _scrape_apec(self, limit):
        count = 0
        for query in SEARCH_QUERIES[:12]:
            try:
                url = f"https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={quote_plus(query)}"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                for card in soup.select('.card-offer, [class*="offer-card"], [class*="result"]')[:limit]:
                    title_el = card.select_one('.card-title, h2, h3, [class*="title"]')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    link = card.select_one('a[href]')
                    href = ''
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('/'):
                            href = f"https://www.apec.fr{href}"
                    loc_el = card.select_one('[class*="location"], [class*="lieu"]')
                    location = loc_el.get_text(strip=True) if loc_el else ''
                    count += self._save_job(title, 'APEC', href, '', location)
                self.stdout.write(f"  APEC '{query}': OK")
            except Exception as e:
                logger.error(f"APEC '{query}': {e}")
        return count

    # ─── INDEED FRANCE ───────────────────────────────────────────────────

    def _scrape_indeed(self, limit):
        count = 0
        for query in SEARCH_QUERIES[:12]:
            try:
                url = f"https://fr.indeed.com/jobs?q={quote_plus(query)}&l=France&limit={limit}"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"  Indeed '{query}': HTTP {resp.status_code}"))
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Indeed uses multiple selectors depending on page version
                job_cards = soup.select(
                    '.job_seen_beacon, .jobsearch-ResultsList .result, '
                    '[data-jk], .tapItem, .resultContent'
                )[:limit]

                for card in job_cards:
                    title_el = card.select_one(
                        '.jobTitle, h2.jobTitle, [class*="jobTitle"], '
                        '.title, a[data-jk]'
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)

                    link = card.select_one('a[href*="/rc/clk"], a[href*="/viewjob"], a[data-jk]')
                    href = ''
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('/'):
                            href = f"https://fr.indeed.com{href}"

                    loc_el = card.select_one('.companyLocation, [class*="location"], .company_location')
                    location = loc_el.get_text(strip=True) if loc_el else ''

                    snippet_el = card.select_one('.job-snippet, [class*="snippet"]')
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ''

                    count += self._save_job(title, 'Indeed', href, snippet, location)

                self.stdout.write(f"  Indeed '{query}': {len(job_cards)} trouvées")
            except Exception as e:
                logger.error(f"Indeed '{query}': {e}")
        return count

    # ─── WELCOME TO THE JUNGLE ───────────────────────────────────────────

    def _scrape_wttj(self, limit):
        count = 0
        for query in SEARCH_QUERIES[:12]:
            try:
                # WTTJ a une API publique pour la recherche
                api_url = (
                    f"https://www.welcometothejungle.com/api/v1/search?"
                    f"query={quote_plus(query)}&page=1&per_page={limit}"
                    f"&aroundLatLng=48.8566,2.3522"
                )
                resp = requests.get(api_url, headers=HEADERS, timeout=15)

                if resp.status_code != 200:
                    # Fallback: scraping HTML
                    html_url = f"https://www.welcometothejungle.com/fr/jobs?query={quote_plus(query)}&refinementList%5Boffices.country_code%5D%5B%5D=FR"
                    resp = requests.get(html_url, headers=HEADERS, timeout=15)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    cards = soup.select('[data-testid="search-results-list-item-wrapper"], article, [class*="ais-Hits-item"]')[:limit]
                    for card in cards:
                        title_el = card.select_one('h3, h4, [class*="title"], [role="heading"]')
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        link = card.select_one('a[href]')
                        href = ''
                        if link and link.get('href'):
                            href = link['href']
                            if href.startswith('/'):
                                href = f"https://www.welcometothejungle.com{href}"
                        loc_el = card.select_one('[class*="location"], [class*="city"]')
                        location = loc_el.get_text(strip=True) if loc_el else ''
                        count += self._save_job(title, 'WTTJ', href, '', location)
                else:
                    # Parse API JSON
                    data = resp.json()
                    for job in data.get('jobs', data.get('results', data.get('hits', [])))[:limit]:
                        title = job.get('name', job.get('title', ''))
                        slug = job.get('slug', '')
                        org_slug = job.get('organization', {}).get('slug', '')
                        href = f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{slug}" if slug else ''
                        desc = job.get('description', job.get('profile', ''))
                        city = job.get('office', {}).get('city', '')
                        count += self._save_job(title, 'WTTJ', href, desc, city)

                self.stdout.write(f"  WTTJ '{query}': OK")
            except Exception as e:
                logger.error(f"WTTJ '{query}': {e}")
        return count

    # ─── FRANCE TRAVAIL (ex Pôle Emploi) ─────────────────────────────────

    def _scrape_france_travail(self, limit):
        """
        France Travail offre une API publique (api.francetravail.io).
        Nécessite un client_id et client_secret (inscription gratuite).
        Fallback sur scraping HTML sinon.
        """
        client_id = os.getenv('FRANCE_TRAVAIL_CLIENT_ID', '')
        client_secret = os.getenv('FRANCE_TRAVAIL_CLIENT_SECRET', '')
        count = 0

        if client_id and client_secret:
            count = self._france_travail_api(client_id, client_secret, limit)
        else:
            self.stdout.write(self.style.WARNING(
                '  FRANCE_TRAVAIL_CLIENT_ID/SECRET non configurés. '
                'Tentative scraping HTML...'
            ))
            count = self._france_travail_scrape(limit)

        return count

    def _france_travail_api(self, client_id, client_secret, limit):
        """Appel API France Travail (api.francetravail.io)."""
        count = 0
        try:
            # 1. Obtenir un token
            token_resp = requests.post(
                'https://entreprise.francetravail.fr/connexion/oauth2/access_token',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'scope': 'api_offresdemploiv2 o2dsoffre',
                },
                params={'realm': '/partenaire'},
                timeout=15,
            )
            token_resp.raise_for_status()
            token = token_resp.json()['access_token']

            # 2. Rechercher des offres
            for query in SEARCH_QUERIES[:12]:
                try:
                    search_resp = requests.get(
                        'https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search',
                        headers={'Authorization': f'Bearer {token}'},
                        params={
                            'motsCles': query,
                            'range': f'0-{limit-1}',
                        },
                        timeout=15,
                    )
                    if search_resp.status_code != 200:
                        continue
                    data = search_resp.json()
                    for offre in data.get('resultats', []):
                        title = offre.get('intitule', '')
                        desc = offre.get('description', '')
                        location = offre.get('lieuTravail', {}).get('libelle', '')
                        url = f"https://candidat.francetravail.fr/offres/recherche/detail/{offre.get('id', '')}"
                        count += self._save_job(title, 'France Travail', url, desc, location)
                    self.stdout.write(f"  France Travail API '{query}': OK")
                except Exception as e:
                    logger.error(f"France Travail API '{query}': {e}")
        except Exception as e:
            logger.error(f"France Travail auth: {e}")
            self.stdout.write(self.style.WARNING(f"  Erreur auth France Travail: {e}"))
        return count

    def _france_travail_scrape(self, limit):
        """Scraping HTML du site France Travail."""
        count = 0
        for query in SEARCH_QUERIES[:4]:
            try:
                url = f"https://candidat.francetravail.fr/offres/recherche?motsCles={quote_plus(query)}&offresPartenaires=true"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.select('[class*="result"], li[class*="result"]')[:limit]
                for card in cards:
                    title_el = card.select_one('h2, [class*="title"], [class*="intitule"]')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    link = card.select_one('a[href]')
                    href = ''
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('/'):
                            href = f"https://candidat.francetravail.fr{href}"
                    loc_el = card.select_one('[class*="location"], [class*="lieu"]')
                    location = loc_el.get_text(strip=True) if loc_el else ''
                    count += self._save_job(title, 'France Travail', href, '', location)
                self.stdout.write(f"  France Travail scrape '{query}': OK")
            except Exception as e:
                logger.error(f"France Travail scrape '{query}': {e}")
        return count

    # ─── HELLOWORK ───────────────────────────────────────────────────────

    def _scrape_hellowork(self, limit):
        count = 0
        for query in SEARCH_QUERIES[:12]:
            try:
                url = f"https://www.hellowork.com/fr-fr/emploi/recherche.html?k={quote_plus(query)}&l=France"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.select('[class*="offer-card"], [class*="job-card"], article')[:limit]
                for card in cards:
                    title_el = card.select_one('h2, h3, [class*="title"]')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    link = card.select_one('a[href]')
                    href = ''
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('/'):
                            href = f"https://www.hellowork.com{href}"
                    loc_el = card.select_one('[class*="location"], [class*="city"]')
                    location = loc_el.get_text(strip=True) if loc_el else ''
                    count += self._save_job(title, 'HelloWork', href, '', location)
                self.stdout.write(f"  HelloWork '{query}': OK")
            except Exception as e:
                logger.error(f"HelloWork '{query}': {e}")
        return count

    # ─── LINKEDIN (public, no login required) ───────────────────────────

    def _scrape_linkedin(self, limit):
        count = 0
        for query in SEARCH_QUERIES:
            try:
                url = (
                    f"https://www.linkedin.com/jobs/search/"
                    f"?keywords={quote_plus(query)}&location=France"
                    f"&f_TPR=r604800&position=1&pageNum=0"
                )
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    self.stdout.write(self.style.WARNING(
                        f"  LinkedIn '{query}': HTTP {resp.status_code}"
                    ))
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.select(
                    '.base-card, .job-search-card, [data-entity-urn]'
                )[:limit]
                for card in cards:
                    title_el = card.select_one(
                        '.base-search-card__title, h3'
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    link = card.select_one(
                        'a.base-card__full-link, a[href*="/jobs/view"]'
                    )
                    href = ''
                    if link and link.get('href'):
                        href = link['href'].split('?')[0]
                    loc_el = card.select_one('.job-search-card__location')
                    location = loc_el.get_text(strip=True) if loc_el else ''
                    company_el = card.select_one(
                        '.base-search-card__subtitle, h4'
                    )
                    company = company_el.get_text(strip=True) if company_el else ''
                    desc = f"{title} - {company}" if company else title
                    count += self._save_job(
                        title, 'LinkedIn', href, desc, location
                    )
                self.stdout.write(
                    f"  LinkedIn '{query}': {len(cards)} trouvées"
                )
            except Exception as e:
                logger.error(f"LinkedIn '{query}': {e}")
        return count

    # ─── DONNÉES D'EXEMPLE ───────────────────────────────────────────────

    def _generate_sample_jobs(self):
        sample_jobs = [
            ('Ingénieur Machine Learning - Santé', 'sante', ['Python', 'TensorFlow', 'Deep Learning'], 'Paris', 'fondamentaux_ia'),
            ('Data Scientist NLP - Finance', 'finance', ['Python', 'NLP', 'LLM'], 'Lyon', 'nlp'),
            ('Chef de projet IA - Transformation', 'industrie', ['AI Strategy'], 'Toulouse', 'management_ia'),
            ('MLOps Engineer - Cloud', 'retail', ['MLOps', 'Docker', 'Cloud ML'], 'Bordeaux', 'deploiement_mlops'),
            ('Responsable Conformité IA - AI Act', 'finance', ['AI Ethics'], 'Paris', 'ia_reglementaire'),
            ('Data Engineer IA - Pipeline', 'energie', ['Python', 'Spark', 'Data Engineering'], 'Nantes', 'data_science'),
            ('Ingénieur IA Maintenance Prédictive - Nucléaire', 'energie', ['Python', 'TensorFlow', 'Deep Learning'], 'Saclay', 'fondamentaux_ia'),
            ('Data Scientist - Optimisation Réseau Électrique', 'energie', ['Python', 'Scikit-learn', 'SQL'], 'Lyon', 'data_science'),
            ('Chef de projet IA - Transition Énergétique', 'energie', ['AI Strategy', 'Cloud ML'], 'Paris', 'management_ia'),
            ('Ingénieur ML - Sûreté Nucléaire & Jumeaux Numériques', 'energie', ['Python', 'PyTorch', 'Deep Learning'], 'Cadarache', 'fondamentaux_ia'),
            ('Analyste IA - Smart Grid & Réseaux Intelligents', 'energie', ['Python', 'Data Engineering', 'SQL'], 'Grenoble', 'ia_decisionnelle'),
            ('Ingénieur Computer Vision - Auto', 'transport', ['Python', 'Computer Vision', 'PyTorch'], 'Toulouse', 'computer_vision'),
            ('Prompt Engineer - IA Générative', 'education', ['LLM', 'NLP'], 'Paris', 'nlp'),
            ('Analyste IA décisionnelle', 'administration', ['SQL', 'Data Visualization'], 'Lille', 'ia_decisionnelle'),
            ('Formateur IA - Deep Learning', 'education', ['TensorFlow', 'PyTorch', 'Deep Learning'], 'Marseille', 'fondamentaux_ia'),
        ]
        for title, sector, skills, loc, training in sample_jobs:
            JobPosting.objects.get_or_create(
                title=title,
                defaults={
                    'source': 'Exemple', 'url': '', 'sector': sector,
                    'skills': skills, 'location': loc,
                    'training_type_match': training, 'relevance_score': 0.8,
                }
            )
        self.stdout.write(f"  {len(sample_jobs)} offres d'exemple générées.")
