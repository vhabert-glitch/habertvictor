"""
Management command : scraping des appels d'offres publics IA depuis le BOAMP.
Source : API BOAMP + fallback données réalistes.
"""
import logging
from datetime import date, timedelta
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from apps.extractor.models import PublicTender
from apps.extractor.classifier import classify_sector

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
}

SEARCH_QUERIES = [
    'intelligence artificielle',
    'machine learning',
    'formation IA',
    'data science',
    'cybersécurité IA',
    'nucléaire IA',
    'deep learning',
    'LLM',
]


class Command(BaseCommand):
    help = 'Scrape les appels d\'offres publics IA depuis le BOAMP et autres sources'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20, help='Résultats max par requête')

    def handle(self, *args, **options):
        limit = options['limit']
        total = 0

        # Try BOAMP API
        total += self._scrape_boamp_api(limit)

        # Try BOAMP HTML scraping
        if total == 0:
            total += self._scrape_boamp_html(limit)

        # Try marchés publics / PLACE
        total += self._scrape_place(limit)

        # Volontairement PAS de repli sur des données d'exemple.
        # C'est ce repli qui a rempli la base de 12 appels d'offres fictifs
        # (échéances inventées, sans URL) pendant que l'API réelle échouait :
        # l'agent les prenait pour de vraies opportunités. Une table vide est
        # une information exacte ; une table de faux ne l'est pas.
        if total == 0:
            self.stdout.write(self.style.ERROR(
                "  Aucun avis récupéré — l'API BOAMP est injoignable ou a changé. "
                "Aucune donnée n'est inventée : la table reste en l'état."
            ))

        self.stdout.write(self.style.SUCCESS(f'\nTotal : {total} appels d\'offres traités.'))

    def _save_tender(self, title, org, description='', budget='',
                     deadline=None, url='', source='BOAMP'):
        """Sauvegarde un appel d'offres avec classification automatique."""
        full_text = f"{title} {description} {org}"
        sector = classify_sector(full_text)
        # Only keep tenders relevant to our sectors
        if sector not in ('cyberdefense', 'energie', 'industrie', 'administration', 'education', 'sante'):
            sector = classify_sector(full_text) or ''

        try:
            _, created = PublicTender.objects.update_or_create(
                title=title[:500],
                org=org[:300],
                defaults={
                    'description': description[:2000],
                    'budget': budget[:100] if budget else '',
                    'deadline': deadline,
                    'sector': sector,
                    'url': url[:1000] if url else '',
                    'source': source,
                }
            )
            return 1 if created else 0
        except Exception as e:
            logger.error(f"Erreur sauvegarde tender: {e}")
            return 0

    # ─── BOAMP API ────────────────────────────────────────────────────────

    def _scrape_boamp_api(self, limit):
        """API BOAMP officielle, exposée par la DILA via Opendatasoft.

        `api.boamp.fr` (visé par la version précédente) n'existe pas : le
        scraper échouait donc systématiquement et retombait sur des données
        d'exemple. Le vrai point d'entrée est l'API Explore v2.1 de la
        plateforme opendata de la DILA, sans authentification :

            https://boamp-datadila.opendatasoft.com/api/explore/v2.1
                /catalog/datasets/boamp/records

        Champs utilisés : `objet` (objet du marché), `nomacheteur` (acheteur
        public), `datelimitereponse` (date limite de réponse — c'est elle qui
        donne de vraies échéances), `dateparution`, `idweb` (identifiant de
        l'avis, qui sert à reconstruire l'URL publique).
        """
        count = 0
        horizon = (date.today() - timedelta(days=730)).isoformat()
        for query in SEARCH_QUERIES:
            try:
                resp = requests.get(
                    'https://boamp-datadila.opendatasoft.com/api/explore/v2.1'
                    '/catalog/datasets/boamp/records',
                    params={
                        # Le BOAMP remonte à plus de dix ans : sans borne de
                        # date, une recherche large ramène des avis clos depuis
                        # 2015, inutiles pour un agenda.
                        'where': (f"search(objet, '{query}') "
                                  f"and dateparution >= date'{horizon}'"),
                        'limit': min(limit, 100),
                        'order_by': 'dateparution desc',
                    },
                    timeout=25,
                )
                if resp.status_code != 200:
                    self.stdout.write(self.style.WARNING(
                        f"  BOAMP '{query}': HTTP {resp.status_code}"))
                    continue

                data = resp.json()
                results = data.get('results', [])
                for avis in results:
                    title = (avis.get('objet') or '').strip()
                    if not title:
                        continue
                    org = (avis.get('nomacheteur') or '').strip()

                    deadline = None
                    for champ in ('datelimitereponse', 'datefindiffusion'):
                        brut = avis.get(champ)
                        if brut:
                            try:
                                deadline = date.fromisoformat(str(brut)[:10])
                                break
                            except ValueError:
                                pass

                    idweb = avis.get('idweb') or ''
                    link = (f'https://www.boamp.fr/pages/avis/?q=idweb:"{idweb}"'
                            if idweb else '')

                    # `objet` est déjà le descriptif du marché ; on garde en plus
                    # le type de procédure, utile pour juger de l'accessibilité.
                    desc = ' — '.join(filter(None, [
                        title,
                        avis.get('procedure_libelle'),
                        avis.get('nature_libelle'),
                        f"paru le {avis.get('dateparution')}" if avis.get('dateparution') else '',
                    ]))

                    count += self._save_tender(
                        title, org, desc, '', deadline, link, 'BOAMP')

                self.stdout.write(
                    f"  BOAMP '{query}': {len(results)} avis "
                    f"(sur {data.get('total_count', '?')} au total)")
            except Exception as e:
                logger.error(f"BOAMP '{query}': {e}")
                self.stdout.write(self.style.WARNING(f"  BOAMP '{query}': {e}"))
        return count

    # ─── BOAMP HTML ───────────────────────────────────────────────────────

    def _scrape_boamp_html(self, limit):
        """Scraping HTML du site BOAMP."""
        count = 0
        for query in SEARCH_QUERIES[:4]:
            try:
                url = f"https://www.boamp.fr/avis/recherche?query={quote_plus(query)}"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.select(
                    '.result-item, .annonce, [class*="avis-item"], '
                    '[class*="search-result"], article'
                )[:limit]

                for card in cards:
                    title_el = card.select_one('h2, h3, [class*="title"], [class*="objet"]')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    org_el = card.select_one('[class*="organisme"], [class*="buyer"]')
                    org = org_el.get_text(strip=True) if org_el else ''
                    link = card.select_one('a[href]')
                    href = ''
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('/'):
                            href = f"https://www.boamp.fr{href}"
                    count += self._save_tender(title, org, '', '', None, href, 'BOAMP')

                self.stdout.write(f"  BOAMP HTML '{query}': OK")
            except Exception as e:
                logger.error(f"BOAMP HTML '{query}': {e}")
        return count

    # ─── PLACE (Plateforme des achats de l'État) ─────────────────────────

    def _scrape_place(self, limit):
        """Tentative scraping de la PLACE (marchés publics de l'État)."""
        count = 0
        for query in SEARCH_QUERIES[:3]:
            try:
                url = (
                    f"https://www.marches-publics.gouv.fr/app/es/search/search.html"
                    f"?query={quote_plus(query)}"
                )
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.select(
                    '.search-result, [class*="consultation"], article, .result-item'
                )[:limit]

                for card in cards:
                    title_el = card.select_one('h2, h3, [class*="title"], [class*="objet"]')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    org_el = card.select_one('[class*="acheteur"], [class*="organisme"]')
                    org = org_el.get_text(strip=True) if org_el else ''
                    link = card.select_one('a[href]')
                    href = ''
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('/'):
                            href = f"https://www.marches-publics.gouv.fr{href}"
                    count += self._save_tender(title, org, '', '', None, href, 'PLACE')

                self.stdout.write(f"  PLACE '{query}': OK")
            except Exception as e:
                logger.error(f"PLACE '{query}': {e}")
        return count

    # ─── DONNÉES D'EXEMPLE ────────────────────────────────────────────────

    def _generate_sample_tenders(self):
        """Génère des appels d'offres réalistes basés sur des marchés publics connus."""
        today = date.today()
        sample_tenders = [
            {
                'title': 'Mise en place d\'outils IA pour l\'analyse de données de défense',
                'org': 'DGA',
                'description': 'Développement et déploiement de solutions d\'intelligence artificielle pour le traitement et l\'analyse de données multi-sources dans le cadre de la défense nationale.',
                'budget': '2,4M€',
                'deadline': today + timedelta(days=22),
                'sector': 'cyberdefense',
                'source': 'BOAMP',
            },
            {
                'title': 'Formation IA dirigeants — Programme BITD',
                'org': 'GICAT',
                'description': 'Programme de formation à l\'intelligence artificielle destiné aux dirigeants et décideurs de la Base Industrielle et Technologique de Défense.',
                'budget': '850K€',
                'deadline': today + timedelta(days=35),
                'sector': 'cyberdefense',
                'source': 'BOAMP',
            },
            {
                'title': 'Étude prospective IA & sûreté nucléaire',
                'org': 'ASN / IRSN',
                'description': 'Étude sur l\'utilisation de l\'intelligence artificielle pour améliorer les processus de sûreté nucléaire et de radioprotection.',
                'budget': '1,2M€',
                'deadline': today + timedelta(days=47),
                'sector': 'energie',
                'source': 'BOAMP',
            },
            {
                'title': 'Plateforme IA de détection d\'intrusions',
                'org': 'ANSSI',
                'description': 'Conception et développement d\'une plateforme basée sur l\'IA pour la détection automatique d\'intrusions et de cybermenaces sur les réseaux des OIV.',
                'budget': '3,1M€',
                'deadline': today + timedelta(days=67),
                'sector': 'cyberdefense',
                'source': 'BOAMP',
            },
            {
                'title': 'IA embarquée pour drones autonomes',
                'org': 'AID',
                'description': 'Développement de modules d\'intelligence artificielle embarquée pour la navigation autonome et la reconnaissance de cibles sur drones militaires.',
                'budget': '5,6M€',
                'deadline': today + timedelta(days=80),
                'sector': 'cyberdefense',
                'source': 'BOAMP',
            },
            {
                'title': 'Jumeau numérique réseau distribution',
                'org': 'Enedis',
                'description': 'Création d\'un jumeau numérique du réseau de distribution électrique intégrant des modèles IA pour l\'optimisation et la maintenance prédictive.',
                'budget': '4,8M€',
                'deadline': today + timedelta(days=90),
                'sector': 'energie',
                'source': 'PLACE',
            },
            {
                'title': 'Optimisation IA parc éolien',
                'org': 'RTE',
                'description': 'Déploiement de solutions d\'intelligence artificielle pour l\'optimisation de la production des parcs éoliens et la prédiction de charge réseau.',
                'budget': '2,1M€',
                'deadline': today + timedelta(days=113),
                'sector': 'energie',
                'source': 'PLACE',
            },
            {
                'title': 'SOC augmenté IA pour OIV',
                'org': 'SGDSN',
                'description': 'Mise en place d\'un Security Operations Center augmenté par l\'intelligence artificielle pour la surveillance des opérateurs d\'importance vitale.',
                'budget': '6,2M€',
                'deadline': today + timedelta(days=86),
                'sector': 'cyberdefense',
                'source': 'BOAMP',
            },
            {
                'title': 'Formation cyber-IA agents DGSI',
                'org': 'MI / DGSI',
                'description': 'Programme de formation en cybersécurité et intelligence artificielle pour les agents de la Direction Générale de la Sécurité Intérieure.',
                'budget': '1,8M€',
                'deadline': today + timedelta(days=106),
                'sector': 'cyberdefense',
                'source': 'BOAMP',
            },
            {
                'title': 'IA prédictive pour maintenance réacteurs nucléaires',
                'org': 'EDF',
                'description': 'Développement de modèles d\'IA prédictive pour la maintenance des composants critiques des réacteurs nucléaires du parc français.',
                'budget': '3,5M€',
                'deadline': today + timedelta(days=75),
                'sector': 'energie',
                'source': 'PLACE',
            },
            {
                'title': 'Plateforme IA de veille stratégique défense',
                'org': 'DRM',
                'description': 'Acquisition d\'une plateforme d\'intelligence artificielle pour l\'analyse automatique de sources ouvertes et la veille stratégique.',
                'budget': '4,2M€',
                'deadline': today + timedelta(days=55),
                'sector': 'cyberdefense',
                'source': 'BOAMP',
            },
            {
                'title': 'Système IA d\'analyse de vulnérabilités réseau',
                'org': 'COMCYBER',
                'description': 'Développement d\'un système automatisé basé sur l\'IA pour l\'identification et la classification des vulnérabilités sur les réseaux de défense.',
                'budget': '2,8M€',
                'deadline': today + timedelta(days=98),
                'sector': 'cyberdefense',
                'source': 'BOAMP',
            },
        ]

        created = 0
        for tender in sample_tenders:
            _, was_created = PublicTender.objects.get_or_create(
                title=tender['title'],
                org=tender['org'],
                defaults={
                    'description': tender['description'],
                    'budget': tender['budget'],
                    'deadline': tender['deadline'],
                    'sector': tender['sector'],
                    'source': tender['source'],
                }
            )
            if was_created:
                created += 1

        self.stdout.write(f"  {created} appels d'offres d'exemple générés.")
