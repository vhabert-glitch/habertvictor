"""
Management command : scraping des formations CPF Open Data + France Compétences RNCP.

Sources :
- CPF Catalogue (API Caisse des Dépôts, sans auth)
- CPF Consommation (formations achetées)
- France Compétences RNCP (CSV data.gouv.fr)
"""
import csv
import io
import logging
import zipfile
import requests
from django.core.management.base import BaseCommand
from apps.extractor.models import FormationCatalog
from apps.extractor.classifier import extract_skills

logger = logging.getLogger(__name__)

# Mots-clés IA pour filtrer les formations pertinentes
IA_KEYWORDS = [
    'intelligence artificielle', 'machine learning', 'deep learning',
    'data science', 'data scientist', 'data analyst', 'data engineer',
    'big data', 'nlp', 'traitement du langage', 'ia', 'artificial intelligence',
    'python data', 'tensorflow', 'pytorch', 'scikit', 'neural',
    'réseau de neurones', 'apprentissage automatique', 'apprentissage profond',
    'chatbot', 'llm', 'gpt', 'ia générative', 'genai', 'prompt',
    'computer vision', 'vision par ordinateur', 'mlops',
    'cloud computing', 'devops', 'docker', 'kubernetes',
    'cybersécurité', 'cyber sécurité', 'blockchain',
    'robotique', 'iot', 'objets connectés',
    'power bi', 'tableau', 'data visualization',
    'analyse de données', 'données massives', 'statistiques',
]

CPF_CATALOGUE_URL = (
    'https://opendata.caissedesdepots.fr/api/explore/v2.1/catalog/datasets/'
    'moncompteformation_catalogueformation/records'
)

CPF_CONSOMMATION_URL = (
    'https://opendata.caissedesdepots.fr/api/explore/v2.1/catalog/datasets/'
    'moncompteformation_formations_engagees/records'
)

RNCP_CSV_URL = (
    'https://www.data.gouv.fr/fr/datasets/r/'
    '26a2b95c-e4fd-4a32-9e01-2a2bc5faf1c5'
)


class Command(BaseCommand):
    help = 'Scrape formations IA depuis CPF Open Data et France Compétences RNCP'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=100,
            help='Nombre max de formations à importer par source',
        )
        parser.add_argument(
            '--source', type=str, default='all',
            help='Source : cpf_catalogue, cpf_conso, rncp, all',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        source = options['source']
        total = 0

        if source in ('all', 'cpf_catalogue'):
            self.stdout.write(self.style.NOTICE('\n--- CPF CATALOGUE ---'))
            total += self._scrape_cpf_catalogue(limit)

        if source in ('all', 'cpf_conso'):
            self.stdout.write(self.style.NOTICE('\n--- CPF CONSOMMATION ---'))
            total += self._scrape_cpf_consommation(limit)

        if source in ('all', 'rncp'):
            self.stdout.write(self.style.NOTICE('\n--- FRANCE COMPÉTENCES RNCP ---'))
            total += self._scrape_rncp(limit)

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal : {total} formations importées/mises à jour.'
        ))

    def _scrape_cpf_catalogue(self, limit):
        """CPF Catalogue via API Caisse des Dépôts (sans auth)."""
        count = 0
        for keyword in IA_KEYWORDS[:20]:
            if count >= limit:
                break
            try:
                params = {
                    'where': f"intitule_formation LIKE '%{keyword}%'",
                    'limit': min(50, limit - count),
                    'select': (
                        'nom_of,intitule_formation,frais_ttc_tot_mean,'
                        'nombre_heures_total_mean,code_rncp,siret'
                    ),
                }
                resp = requests.get(
                    CPF_CATALOGUE_URL, params=params, timeout=30,
                )
                if resp.status_code != 200:
                    logger.warning(f'CPF catalogue {keyword}: HTTP {resp.status_code}')
                    continue

                data = resp.json()
                results = data.get('results', [])

                for record in results:
                    name = record.get('intitule_formation', '')
                    provider = record.get('nom_of', '')
                    if not name:
                        continue

                    price_raw = record.get('frais_ttc_tot_mean')
                    price = f"{int(price_raw)} €" if price_raw else ''
                    hours = record.get('nombre_heures_total_mean')
                    duration = f"{int(hours)}h" if hours else ''

                    _, created = FormationCatalog.objects.update_or_create(
                        name=name[:500],
                        provider=provider[:300] if provider else 'CPF',
                        defaults={
                            'training_type': 'certification',
                            'price': price,
                            'duration': duration,
                            'description': f"Formation CPF - {name}. "
                                           f"Code RNCP: {record.get('code_rncp', 'N/C')}",
                            'format': 'hybride',
                            'url': '',
                        }
                    )
                    if created:
                        count += 1

                self.stdout.write(f"  CPF catalogue '{keyword}': {len(results)} résultats")
            except Exception as e:
                logger.error(f"CPF catalogue '{keyword}': {e}")

        self.stdout.write(f'  → {count} formations CPF catalogue importées')
        return count

    def _scrape_cpf_consommation(self, limit):
        """CPF Consommation (formations les plus achetées)."""
        count = 0
        for keyword in IA_KEYWORDS[:15]:
            if count >= limit:
                break
            try:
                params = {
                    'where': f"intitule_certification LIKE '%{keyword}%'",
                    'limit': min(50, limit - count),
                    'order_by': 'nb_dossiers DESC',
                    'select': (
                        'intitule_certification,nb_dossiers,montant_engage,'
                        'prix_moyen,duree_moyenne'
                    ),
                }
                resp = requests.get(
                    CPF_CONSOMMATION_URL, params=params, timeout=30,
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                results = data.get('results', [])

                for record in results:
                    name = record.get('intitule_certification', '')
                    if not name:
                        continue

                    nb_dossiers = record.get('nb_dossiers', 0)
                    prix_moyen = record.get('prix_moyen')
                    price = f"{int(prix_moyen)} €" if prix_moyen else ''
                    duree = record.get('duree_moyenne')
                    duration = f"{int(duree)}h" if duree else ''

                    _, created = FormationCatalog.objects.update_or_create(
                        name=name[:500],
                        provider='CPF (formations achetées)',
                        defaults={
                            'training_type': 'certification',
                            'price': price,
                            'duration': duration,
                            'description': (
                                f"Formation CPF populaire - {name}. "
                                f"{nb_dossiers} dossiers engagés."
                            ),
                            'format': 'hybride',
                            'url': '',
                        }
                    )
                    if created:
                        count += 1

                self.stdout.write(f"  CPF conso '{keyword}': {len(results)} résultats")
            except Exception as e:
                logger.error(f"CPF conso '{keyword}': {e}")

        self.stdout.write(f'  → {count} formations CPF consommation importées')
        return count

    def _scrape_rncp(self, limit):
        """France Compétences RNCP (CSV data.gouv.fr)."""
        count = 0
        try:
            self.stdout.write('  Téléchargement du fichier RNCP...')
            resp = requests.get(RNCP_CSV_URL, timeout=60, stream=True)
            if resp.status_code != 200:
                self.stdout.write(self.style.WARNING(
                    f'  RNCP: HTTP {resp.status_code}, skip.'
                ))
                return 0

            content = resp.content
            # Try ZIP first, fallback to raw CSV
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    csv_names = [n for n in zf.namelist() if n.endswith('.csv')]
                    if not csv_names:
                        self.stdout.write(self.style.WARNING('  Aucun CSV dans le ZIP'))
                        return 0
                    csv_data = zf.read(csv_names[0]).decode('utf-8', errors='replace')
            except zipfile.BadZipFile:
                csv_data = content.decode('utf-8', errors='replace')

            reader = csv.DictReader(io.StringIO(csv_data), delimiter=';')

            # Codes ROME liés à l'IA/data/numérique
            ia_rome_prefixes = ['M18', 'M17']
            ia_formacode_keywords = [
                'intelligence artificielle', 'informatique', 'data',
                'numérique', 'digital', 'programmation', 'réseau',
            ]

            for row in reader:
                if count >= limit:
                    break

                intitule = row.get('INTITULE', row.get('Intitule', ''))
                codes_rome = row.get('CODES_ROME', row.get('Code(s) ROME', ''))
                certificateurs = row.get('CERTIFICATEURS', row.get('Certificateur(s)', ''))
                capacites = row.get('CAPACITES_ATTESTEES', row.get('Activités visées', ''))
                blocs = row.get('blocs_competences_libelles', row.get('Blocs de compétences', ''))

                if not intitule:
                    continue

                # Filtrage : codes ROME M18xx OU mots-clés IA dans le titre/capacités
                full_text = f"{intitule} {capacites} {blocs}".lower()
                rome_match = any(
                    prefix.lower() in codes_rome.lower()
                    for prefix in ia_rome_prefixes
                ) if codes_rome else False
                keyword_match = any(kw in full_text for kw in ia_formacode_keywords)

                if not rome_match and not keyword_match:
                    continue

                # Vérifier pertinence IA plus stricte
                ia_match = any(kw in full_text for kw in IA_KEYWORDS[:15])
                if not ia_match and not rome_match:
                    continue

                description = capacites[:2000] if capacites else ''
                if blocs:
                    description += f'\nBlocs de compétences : {blocs[:500]}'

                _, created = FormationCatalog.objects.update_or_create(
                    name=intitule[:500],
                    provider=certificateurs[:300] if certificateurs else 'France Compétences',
                    defaults={
                        'training_type': 'certification',
                        'description': description,
                        'format': '',
                        'url': '',
                    }
                )
                if created:
                    count += 1

            self.stdout.write(f'  → {count} certifications RNCP importées')
        except Exception as e:
            logger.error(f'RNCP: {e}')
            self.stdout.write(self.style.ERROR(f'  Erreur RNCP: {e}'))

        return count
