"""
Management command : scraping des formations IA existantes sur le marché français.
Sources : catalogues d'organismes, scraping web + fallback données de référence.
"""
import logging
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from apps.extractor.models import FormationCatalog
from apps.extractor.classifier import classify_sector

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
}

SEARCH_QUERIES = [
    'formation intelligence artificielle',
    'executive certificate IA',
    'formation machine learning',
    'formation data science',
    'formation cybersécurité IA',
    'formation IA énergie nucléaire',
    'certificat IA dirigeants',
    'master intelligence artificielle',
]


class Command(BaseCommand):
    help = 'Scrape les formations IA existantes sur le marché français'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20, help='Résultats max par requête')

    def handle(self, *args, **options):
        limit = options['limit']
        total = 0

        # Try Mon Compte Formation API
        total += self._scrape_mcf(limit)

        # Try scraping formation catalog sites
        total += self._scrape_catalogs(limit)

        # Volontairement PAS de repli sur des données de référence.
        # Ce repli s'exécutait à chaque passage puisque l'API visée
        # (api-cpf.moncompteformation.gouv.fr) n'existe pas : la table gonflait
        # de formations inventées, sans URL, run après run. Or c'est LA table
        # qui sert de référence pour dire « ce besoin n'est couvert par aucune
        # formation » — la remplir de faux rendait cette analyse trompeuse.
        if total == 0:
            self.stdout.write(self.style.ERROR(
                "  Aucune formation récupérée. Aucune donnée n'est inventée : "
                "il faut rebrancher une source réelle (API France Travail "
                "« Open formation », ou catalogue open data)."
            ))

        self.stdout.write(self.style.SUCCESS(f'\nTotal : {total} formations traitées.'))

    def _save_formation(self, name, provider, description='', price='',
                        training_type='', format='', duration='',
                        url='', sector=''):
        """Sauvegarde une formation avec classification automatique."""
        if not sector:
            full_text = f"{name} {description} {provider}"
            sector = classify_sector(full_text)

        try:
            _, created = FormationCatalog.objects.update_or_create(
                name=name[:500],
                provider=provider[:300],
                defaults={
                    'sector': sector,
                    'training_type': training_type,
                    'url': url[:1000] if url else '',
                    'price': price[:100] if price else '',
                    'format': format,
                    'duration': duration[:100] if duration else '',
                    'description': description[:2000],
                }
            )
            return 1 if created else 0
        except Exception as e:
            logger.error(f"Erreur sauvegarde formation: {e}")
            return 0

    # ─── MON COMPTE FORMATION ─────────────────────────────────────────────

    def _scrape_mcf(self, limit):
        """Scraping de Mon Compte Formation."""
        count = 0
        for query in SEARCH_QUERIES[:4]:
            try:
                url = (
                    f"https://www.moncompteformation.gouv.fr/espace-prive/html/"
                    f"#/formation/recherche?q={quote_plus(query)}"
                )
                # MCF is a SPA, try their API endpoint
                api_url = (
                    f"https://api-cpf.moncompteformation.gouv.fr/api/public/v1/"
                    f"formations?q={quote_plus(query)}&size={limit}"
                )
                resp = requests.get(api_url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                results = data.get('content', data.get('results', []))
                for item in results:
                    name = item.get('intitule', item.get('title', ''))
                    if not name:
                        continue
                    provider = item.get('organisme', {}).get('nom', item.get('provider', ''))
                    price = item.get('prix', item.get('price', ''))
                    if price and not str(price).endswith('€'):
                        price = f"{price}€"
                    duration = item.get('duree', item.get('duration', ''))
                    count += self._save_formation(
                        name, provider, '', str(price),
                        'certification', '', str(duration)
                    )

                self.stdout.write(f"  MCF '{query}': {len(results)} résultats")
            except Exception as e:
                logger.error(f"MCF '{query}': {e}")
        return count

    # ─── CATALOGUES DE FORMATIONS ─────────────────────────────────────────

    def _scrape_catalogs(self, limit):
        """Scraping de sites de catalogues de formations."""
        count = 0

        # Try various formation catalog sites
        catalog_urls = [
            ('https://www.kelformation.com/formation/domaine/intelligence-artificielle', 'KelFormation'),
            ('https://www.maformation.fr/formation/intelligence-artificielle', 'MaFormation'),
        ]

        for base_url, source_name in catalog_urls:
            try:
                resp = requests.get(base_url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.select(
                    '.training-card, .formation-item, article, '
                    '[class*="formation"], [class*="training"], .result-item'
                )[:limit]

                for card in cards:
                    title_el = card.select_one('h2, h3, [class*="title"], [class*="name"]')
                    if not title_el:
                        continue
                    name = title_el.get_text(strip=True)

                    org_el = card.select_one('[class*="organisme"], [class*="provider"], [class*="school"]')
                    provider = org_el.get_text(strip=True) if org_el else source_name

                    price_el = card.select_one('[class*="price"], [class*="prix"], [class*="tarif"]')
                    price = price_el.get_text(strip=True) if price_el else ''

                    duration_el = card.select_one('[class*="duration"], [class*="duree"]')
                    duration = duration_el.get_text(strip=True) if duration_el else ''

                    link = card.select_one('a[href]')
                    href = ''
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('/'):
                            href = f"{base_url.split('/')[0]}//{base_url.split('/')[2]}{href}"

                    count += self._save_formation(name, provider, '', price, '', '', duration, href)

                self.stdout.write(f"  {source_name}: OK")
            except Exception as e:
                logger.error(f"{source_name}: {e}")

        return count

    # ─── DONNÉES DE RÉFÉRENCE ─────────────────────────────────────────────

    def _generate_reference_formations(self):
        """Génère des formations de référence connues sur le marché français."""
        formations = [
            # === Formations transversales / Vue globale ===
            {
                'name': 'Executive Certificate IA & Défense',
                'provider': 'CentraleSupélec Exed',
                'price': '8 500€',
                'sector': 'cyberdefense',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '6 mois',
                'description': 'Programme executive certifiant en intelligence artificielle appliquée aux enjeux de défense et de souveraineté.',
            },
            {
                'name': 'IA pour Dirigeants',
                'provider': 'HEC Paris',
                'price': '12 000€',
                'sector': '',
                'training_type': 'executive',
                'format': 'presentiel',
                'duration': '5 jours',
                'description': 'Programme intensif pour dirigeants sur les enjeux stratégiques de l\'IA et sa mise en œuvre en entreprise.',
            },
            {
                'name': 'Management de l\'IA',
                'provider': 'ESSEC',
                'price': '9 800€',
                'sector': '',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '4 mois',
                'description': 'Certificat en management de l\'intelligence artificielle pour cadres et décideurs.',
            },
            {
                'name': 'IA & Transformation',
                'provider': 'Polytechnique ExEd',
                'price': '7 200€',
                'sector': '',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '3 mois',
                'description': 'Programme de transformation digitale par l\'IA pour les managers et dirigeants.',
            },
            {
                'name': 'Certificat IA Appliquée',
                'provider': 'Sciences Po ExEd',
                'price': '6 500€',
                'sector': '',
                'training_type': 'certification',
                'format': 'hybride',
                'duration': '3 mois',
                'description': 'Certificat en IA appliquée aux politiques publiques et à la gouvernance.',
            },
            {
                'name': 'IA & Cybersécurité',
                'provider': 'Télécom Paris ExEd',
                'price': '5 800€',
                'sector': 'cyberdefense',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '4 mois',
                'description': 'Formation avancée combinant intelligence artificielle et cybersécurité.',
            },
            # === Formations Défense ===
            {
                'name': 'IA pour l\'industrie de défense',
                'provider': 'ISAE-SUPAERO',
                'price': '7 200€',
                'sector': 'cyberdefense',
                'training_type': 'executive',
                'format': 'presentiel',
                'duration': '5 jours',
                'description': 'Formation spécialisée en IA pour les applications de défense et d\'aéronautique.',
            },
            {
                'name': 'Cyberdéfense & IA',
                'provider': 'École de Guerre Éco',
                'price': '4 800€',
                'sector': 'cyberdefense',
                'training_type': 'courte',
                'format': 'presentiel',
                'duration': '3 jours',
                'description': 'Formation en cyberdéfense intégrant les outils d\'intelligence artificielle.',
            },
            {
                'name': 'Programme DGA-IA',
                'provider': 'DGA / Polytechnique',
                'price': 'Interne',
                'sector': 'cyberdefense',
                'training_type': 'interne',
                'format': 'presentiel',
                'duration': '12 mois',
                'description': 'Programme interne de formation IA pour les ingénieurs et cadres de la DGA.',
            },
            # === Formations Énergie ===
            {
                'name': 'IA pour l\'Énergie',
                'provider': 'IFP School',
                'price': '6 800€',
                'sector': 'energie',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '4 mois',
                'description': 'Programme sur l\'application de l\'IA dans le secteur énergétique.',
            },
            {
                'name': 'Digital Twin Industriel',
                'provider': 'Arts & Métiers ExEd',
                'price': '5 400€',
                'sector': 'energie',
                'training_type': 'courte',
                'format': 'presentiel',
                'duration': '3 jours',
                'description': 'Formation sur les jumeaux numériques et leur application dans l\'industrie énergétique.',
            },
            {
                'name': 'IA & Transition Énergétique',
                'provider': 'Mines Paris ExEd',
                'price': '7 600€',
                'sector': 'energie',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '5 mois',
                'description': 'Programme IA appliquée à la transition énergétique et écologique.',
            },
            {
                'name': 'Sûreté nucléaire & IA',
                'provider': 'INSTN / CEA',
                'price': '4 200€',
                'sector': 'energie',
                'training_type': 'courte',
                'format': 'presentiel',
                'duration': '4 jours',
                'description': 'Formation sur l\'utilisation de l\'IA pour les enjeux de sûreté nucléaire.',
            },
            {
                'name': 'Data Science pour l\'énergie',
                'provider': 'ENSAE / IP Paris',
                'price': '5 900€',
                'sector': 'energie',
                'training_type': 'certification',
                'format': 'hybride',
                'duration': '3 mois',
                'description': 'Certificat en data science appliquée aux problématiques énergétiques.',
            },
            # === Formations Cybersécurité ===
            {
                'name': 'Cyberdéfense avancée',
                'provider': 'ANSSI / CNAM',
                'price': '3 200€',
                'sector': 'cyberdefense',
                'training_type': 'certification',
                'format': 'hybride',
                'duration': '6 mois',
                'description': 'Formation certifiante en cyberdéfense avancée, incluant les outils IA.',
            },
            {
                'name': 'SOC & Intelligence Artificielle',
                'provider': 'Thales Academy',
                'price': 'Interne',
                'sector': 'cyberdefense',
                'training_type': 'interne',
                'format': 'presentiel',
                'duration': '5 jours',
                'description': 'Formation interne sur l\'augmentation du SOC par l\'intelligence artificielle.',
            },
            {
                'name': 'Red Team & IA offensive',
                'provider': 'Quarkslab / ESIEA',
                'price': '4 600€',
                'sector': 'cyberdefense',
                'training_type': 'courte',
                'format': 'presentiel',
                'duration': '3 jours',
                'description': 'Formation en techniques offensives de cybersécurité utilisant l\'IA.',
            },
            {
                'name': 'Gouvernance IA & Conformité',
                'provider': 'Université Paris-Dauphine',
                'price': '5 200€',
                'sector': '',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '4 mois',
                'description': 'Programme de gouvernance de l\'IA incluant la conformité EU AI Act.',
            },
            {
                'name': 'Master Spécialisé IA',
                'provider': 'CentraleSupélec',
                'price': '18 500€',
                'sector': '',
                'training_type': 'diplome',
                'format': 'presentiel',
                'duration': '12 mois',
                'description': 'Master spécialisé en intelligence artificielle, couvrant ML, DL, NLP et Computer Vision.',
            },
            {
                'name': 'IA & Défense nationale',
                'provider': 'IHEDN',
                'price': '2 800€',
                'sector': 'cyberdefense',
                'training_type': 'courte',
                'format': 'presentiel',
                'duration': '2 jours',
                'description': 'Séminaire sur les enjeux de l\'IA dans le contexte de la défense nationale.',
            },
            # === IA Générative, LLM, RAG ===
            {
                'name': 'LLM en production : fine-tuning, RAG et déploiement',
                'provider': 'Hugging Face / Orsys',
                'price': '3 900€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '5 jours',
                'description': 'Formation pratique sur les LLM : fine-tuning avec LoRA/QLoRA, RAG avec LangChain, vector databases (FAISS, ChromaDB), prompt engineering avancé et déploiement.',
            },
            {
                'name': 'IA Générative pour développeurs : LangChain & AI Agents',
                'provider': 'DataScientest',
                'price': '2 800€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '4 jours',
                'description': 'Développement d\'applications IA générative avec LangChain, LangGraph, AI Agents autonomes, vector databases et RAG. Mise en production avec Docker et Kubernetes.',
            },
            {
                'name': 'Prompt Engineering & IA Générative',
                'provider': 'Jedha Bootcamp',
                'price': '1 500€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'Maîtriser le prompt engineering pour GPT, Claude et Mistral. Techniques avancées : chain-of-thought, few-shot, RAG et agents.',
            },
            {
                'name': 'Architecte Solutions RAG & Vector Databases',
                'provider': 'OCTO Academy',
                'price': '3 200€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Concevoir et déployer des architectures RAG en entreprise. Choix de vector databases (Pinecone, Weaviate, Qdrant), chunking, embedding, retrieval et évaluation.',
            },
            {
                'name': 'Fine-tuning de LLM : de la théorie à la pratique',
                'provider': 'Hugging Face Academy',
                'price': '2 400€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '3 jours',
                'description': 'Fine-tuning de modèles Hugging Face avec PEFT, LoRA, QLoRA. RLHF et alignement. Évaluation et benchmark de LLM.',
            },
            # === MLOps & Infrastructure ===
            {
                'name': 'MLOps : du modèle au déploiement en production',
                'provider': 'Orsys',
                'price': '3 400€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '5 jours',
                'description': 'Pipeline MLOps complet : MLflow, Docker, Kubernetes, CI/CD pour le ML, monitoring de modèles, drift detection.',
            },
            {
                'name': 'Kubernetes pour la Data Science & le ML',
                'provider': 'Adaltas',
                'price': '2 900€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '4 jours',
                'description': 'Orchestration de workloads ML avec Kubernetes : Kubeflow, serving de modèles, GPU scheduling, Helm charts, Terraform pour l\'infra cloud.',
            },
            {
                'name': 'Infrastructure as Code pour le ML : Terraform & Cloud',
                'provider': 'WeScale',
                'price': '2 600€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '3 jours',
                'description': 'Provisionner l\'infrastructure ML avec Terraform sur AWS/GCP/Azure. Docker, Kubernetes, pipelines CI/CD pour le déploiement de modèles.',
            },
            {
                'name': 'Cloud ML : AWS SageMaker, Azure ML & Vertex AI',
                'provider': 'M2i Formation',
                'price': '3 100€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '5 jours',
                'description': 'Formation multi-cloud pour le ML : entraînement, déploiement et monitoring de modèles sur AWS SageMaker, Azure ML et Google Vertex AI.',
            },
            # === Python, Data Science & ML ===
            {
                'name': 'Python pour la Data Science & le Machine Learning',
                'provider': 'OpenClassrooms',
                'price': '600€/mois',
                'sector': '',
                'training_type': 'certification',
                'format': 'elearning',
                'duration': '6 mois',
                'description': 'Parcours certifiant Python, NumPy, Pandas, Scikit-learn, SQL, data engineering et visualisation de données.',
            },
            {
                'name': 'Deep Learning avec PyTorch',
                'provider': 'Orsys',
                'price': '2 800€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Formation pratique PyTorch : réseaux de neurones, CNN, RNN, transformers, transfer learning et déploiement.',
            },
            {
                'name': 'Deep Learning avec TensorFlow & Keras',
                'provider': 'PLB Consultant',
                'price': '2 700€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Maîtriser TensorFlow et Keras pour le deep learning : CNN, NLP, séries temporelles, déploiement avec TF Serving.',
            },
            {
                'name': 'NLP avancé & Traitement du Langage Naturel',
                'provider': 'DataScientest',
                'price': '3 200€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '5 jours',
                'description': 'NLP avancé : transformers, BERT, GPT, Hugging Face, spaCy, text mining, analyse de sentiments et chatbots.',
            },
            {
                'name': 'Computer Vision & Deep Learning',
                'provider': 'Ynov / DataScientest',
                'price': '2 900€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Vision par ordinateur avec Python, OpenCV, YOLO, détection d\'objets, segmentation, reconnaissance faciale et OCR.',
            },
            {
                'name': 'Data Engineering : pipelines, SQL & Spark',
                'provider': 'Jedha Bootcamp',
                'price': '6 995€',
                'sector': '',
                'training_type': 'certification',
                'format': 'hybride',
                'duration': '3 mois',
                'description': 'Bootcamp Data Engineering : Python, SQL avancé, Apache Spark, ETL, data pipelines, cloud (AWS/GCP) et orchestration.',
            },
            {
                'name': 'Bootcamp Data Scientist',
                'provider': 'Le Wagon',
                'price': '7 900€',
                'sector': '',
                'training_type': 'certification',
                'format': 'presentiel',
                'duration': '9 semaines',
                'description': 'Bootcamp intensif : Python, SQL, machine learning avec Scikit-learn, deep learning, MLOps et projet de fin de formation.',
            },
            # === Gouvernance, Éthique & AI Safety ===
            {
                'name': 'AI Governance & Conformité EU AI Act',
                'provider': 'Wavestone Academy',
                'price': '4 200€',
                'sector': '',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'Gouvernance IA en entreprise : AI Act, classification des risques, registre IA, audit algorithmique, AI governance framework.',
            },
            {
                'name': 'AI Safety & Alignement : enjeux et pratiques',
                'provider': 'ENS Paris-Saclay',
                'price': '1 800€',
                'sector': '',
                'training_type': 'courte',
                'format': 'presentiel',
                'duration': '2 jours',
                'description': 'Formation sur les enjeux de sûreté de l\'IA : alignement, robustesse, red-teaming de LLM, AI safety et risques existentiels.',
            },
            {
                'name': 'Éthique de l\'IA & IA Responsable',
                'provider': 'Institut Montaigne / Dauphine',
                'price': '3 500€',
                'sector': '',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'Éthique de l\'IA, biais algorithmiques, explicabilité, IA responsable, impact social et gouvernance des données.',
            },
            # === Formations sectorielles ===
            {
                'name': 'IA appliquée à la Santé & Imagerie Médicale',
                'provider': 'Université Paris Cité',
                'price': '4 500€',
                'sector': 'sante',
                'training_type': 'certification',
                'format': 'hybride',
                'duration': '4 mois',
                'description': 'IA pour la santé : imagerie médicale avec deep learning, NLP sur dossiers patients, diagnostic assisté, Python et PyTorch.',
            },
            {
                'name': 'Data Science pour la Pharma & Clinical Trials',
                'provider': 'CESAM / Paris-Saclay',
                'price': '5 200€',
                'sector': 'sante',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '3 mois',
                'description': 'Data science appliquée à la pharma : essais cliniques, pharmacovigilance, drug discovery, biostatistiques et Python.',
            },
            {
                'name': 'IA pour l\'Industrie 4.0 & Maintenance Prédictive',
                'provider': 'Arts & Métiers / Cetim',
                'price': '3 800€',
                'sector': 'industrie',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'IA pour l\'industrie : maintenance prédictive, digital twin, IoT industriel, computer vision qualité, Python et TensorFlow.',
            },
            {
                'name': 'Robotique & IA : Vision et Navigation Autonome',
                'provider': 'ENSTA Paris',
                'price': '4 600€',
                'sector': 'industrie',
                'training_type': 'courte',
                'format': 'presentiel',
                'duration': '5 jours',
                'description': 'Robotique intelligente : computer vision, SLAM, navigation autonome, reinforcement learning, ROS et PyTorch.',
            },
            {
                'name': 'IA pour la Finance : Trading, Risque & Conformité',
                'provider': 'ENSAE / Quantmetry',
                'price': '4 800€',
                'sector': 'finance',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Machine learning pour la finance : scoring de crédit, détection de fraude, NLP réglementaire, Python et Scikit-learn.',
            },
            # === MOOCs et formations en ligne ===
            {
                'name': 'Machine Learning Specialization',
                'provider': 'Coursera / Stanford (Andrew Ng)',
                'price': '49€/mois',
                'sector': '',
                'training_type': 'mooc',
                'format': 'elearning',
                'duration': '3 mois',
                'description': 'Spécialisation complète en ML : régression, classification, deep learning avec TensorFlow, Python et Scikit-learn.',
            },
            {
                'name': 'Deep Learning Specialization',
                'provider': 'Coursera / deeplearning.ai',
                'price': '49€/mois',
                'sector': '',
                'training_type': 'mooc',
                'format': 'elearning',
                'duration': '4 mois',
                'description': 'Spécialisation deep learning : réseaux de neurones, CNN, RNN, transformers avec TensorFlow et Python.',
            },
            {
                'name': 'Generative AI with LLMs',
                'provider': 'Coursera / AWS & deeplearning.ai',
                'price': '49€/mois',
                'sector': '',
                'training_type': 'mooc',
                'format': 'elearning',
                'duration': '1 mois',
                'description': 'IA générative : fonctionnement des LLM, fine-tuning, RLHF, prompt engineering, RAG et déploiement sur AWS.',
            },
            {
                'name': 'MLOps Specialization',
                'provider': 'Coursera / deeplearning.ai',
                'price': '49€/mois',
                'sector': '',
                'training_type': 'mooc',
                'format': 'elearning',
                'duration': '4 mois',
                'description': 'MLOps : pipelines ML, TFX, data validation, model monitoring, CI/CD pour le ML, Docker et Kubernetes.',
            },
            {
                'name': 'Hugging Face NLP Course',
                'provider': 'Hugging Face',
                'price': 'Gratuit',
                'sector': '',
                'training_type': 'mooc',
                'format': 'elearning',
                'duration': '2 mois',
                'description': 'Cours gratuit NLP avec Hugging Face Transformers : tokenisation, fine-tuning BERT/GPT, datasets et modèle hub.',
            },
            # === AI Strategy & Leadership ===
            {
                'name': 'Stratégie IA pour Comex & Dirigeants',
                'provider': 'McKinsey Academy / HEC',
                'price': '8 900€',
                'sector': '',
                'training_type': 'executive',
                'format': 'presentiel',
                'duration': '4 jours',
                'description': 'AI Strategy pour dirigeants : roadmap IA, business cases, ROI, conduite du changement, transformation digitale et innovation.',
            },
            {
                'name': 'Chief AI Officer : piloter la stratégie IA',
                'provider': 'Polytechnique ExEd',
                'price': '9 500€',
                'sector': '',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '5 jours',
                'description': 'Programme pour futurs Chief AI Officer : AI strategy, gouvernance, build vs buy, recrutement data/IA, innovation et transformation digitale.',
            },
            {
                'name': 'AI Strategy & Innovation : de l\'idée au déploiement',
                'provider': 'INSEAD ExEd',
                'price': '11 000€',
                'sector': '',
                'training_type': 'executive',
                'format': 'presentiel',
                'duration': '5 jours',
                'description': 'Stratégie d\'innovation par l\'IA : design thinking, POC, scale-up, R&D, veille technologique et disruption.',
            },
            {
                'name': 'R&D et Innovation IA en entreprise',
                'provider': 'Mines ParisTech ExEd',
                'price': '6 200€',
                'sector': '',
                'training_type': 'executive',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Piloter la R&D IA : proof of concept, open innovation, lab innovation, veille technologique, incubation et accélération.',
            },
            # === AI Agents avancé ===
            {
                'name': 'AI Agents & Systèmes Multi-Agents en production',
                'provider': 'OCTO Academy',
                'price': '3 600€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '4 jours',
                'description': 'Construire des AI Agents autonomes avec LangGraph, CrewAI et AutoGen. Orchestration multi-agents, RAG agentic, tool use et déploiement.',
            },
            {
                'name': 'Développeur AI Agents : LangChain, LangGraph & Tool Use',
                'provider': 'Zenika',
                'price': '2 800€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '3 jours',
                'description': 'Développement d\'AI Agents avec LangChain et LangGraph : planification, mémoire, tool calling, RAG avancé et déploiement Docker.',
            },
            # === MLOps renforcé ===
            {
                'name': 'MLOps avancé : Kubeflow, Seldon & Feature Stores',
                'provider': 'Adaltas',
                'price': '3 500€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '4 jours',
                'description': 'MLOps avancé : Kubeflow Pipelines, Seldon Core, feature stores (Feast), model registry, A/B testing, monitoring et Kubernetes.',
            },
            {
                'name': 'Pipeline ML de bout en bout avec MLflow & Docker',
                'provider': 'PLB Consultant',
                'price': '2 600€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'MLOps pratique : MLflow tracking, model registry, Docker, CI/CD pour le ML, déploiement avec FastAPI et monitoring.',
            },
            # === Data Governance & Data Management ===
            {
                'name': 'Data Governance & Data Management',
                'provider': 'DAMA France / Orsys',
                'price': '3 200€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Gouvernance des données : data management, data quality, data catalog, MDM, RGPD, data lineage et data governance framework.',
            },
            {
                'name': 'Data Steward & Qualité des Données',
                'provider': 'EBG / Micropole Academy',
                'price': '2 400€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'Rôle de Data Steward : data governance, qualité des données, data catalog, métadonnées et conformité RGPD.',
            },
            # === Computer Vision renforcé ===
            {
                'name': 'Computer Vision industrielle : détection & segmentation',
                'provider': 'CNAM / Orsys',
                'price': '3 100€',
                'sector': 'industrie',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Vision par ordinateur appliquée : YOLO, détection d\'objets, segmentation sémantique, OCR, contrôle qualité avec Python et OpenCV.',
            },
            {
                'name': 'Vision par ordinateur : de OpenCV aux modèles génératifs',
                'provider': 'DataScientest',
                'price': '2 900€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '4 jours',
                'description': 'Computer vision complète : OpenCV, CNN, transfert learning, détection d\'objets YOLO, segmentation, GANs et diffusion models avec PyTorch.',
            },
            # === Data Visualization ===
            {
                'name': 'Data Visualization : Tableau, Power BI & Python',
                'provider': 'M2i Formation',
                'price': '2 800€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Data visualization avancée : Tableau, Power BI, Matplotlib, Seaborn, Plotly, storytelling data et dashboarding.',
            },
            {
                'name': 'Dashboarding & Reporting IA',
                'provider': 'Orsys',
                'price': '2 100€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'Concevoir des dashboards IA : data visualization, KPI, reporting automatisé, Power BI et intégration de modèles ML.',
            },
            # === AI Ethics renforcé ===
            {
                'name': 'Auditer les algorithmes : biais, équité & explicabilité',
                'provider': 'Télécom Paris ExEd',
                'price': '3 400€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'Audit algorithmique : détection de biais, métriques d\'équité, explicabilité (SHAP, LIME), IA responsable et conformité AI Act.',
            },
            # === Agile & Gestion de projet IA ===
            {
                'name': 'Gestion de projet IA : Agile, Scrum & Design Thinking',
                'provider': 'Orsys',
                'price': '2 600€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'Piloter des projets IA avec Agile et Scrum. Design thinking appliqué à l\'IA, lean startup, sprints data et rétrospectives.',
            },
            {
                'name': 'Product Management IA & Data Products',
                'provider': 'Thiga Academy',
                'price': '2 400€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '3 jours',
                'description': 'Product management pour produits IA : discovery, agile data, MVP, user research, métriques ML et go-to-market.',
            },
            # === SQL & Data renforcé ===
            {
                'name': 'SQL avancé pour la Data Science',
                'provider': 'PLB Consultant',
                'price': '2 200€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '3 jours',
                'description': 'SQL avancé : window functions, CTE, optimisation de requêtes, modélisation données, PostgreSQL et intégration Python.',
            },
            {
                'name': 'Big Data : Spark, Hadoop & Data Lakes',
                'provider': 'Adaltas',
                'price': '3 400€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '4 jours',
                'description': 'Architecture Big Data : Apache Spark, PySpark, Hadoop, data lakes, Delta Lake, streaming et orchestration.',
            },
            # === Cloud ML renforcé ===
            {
                'name': 'Google Cloud AI & Vertex AI',
                'provider': 'Google Cloud / Revolve',
                'price': '2 800€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '3 jours',
                'description': 'Plateforme Google Cloud pour le ML : Vertex AI, AutoML, Generative AI Studio, BigQuery ML et déploiement de modèles.',
            },
            {
                'name': 'AWS Machine Learning Specialty',
                'provider': 'AWS / Orsys',
                'price': '3 000€',
                'sector': '',
                'training_type': 'certification',
                'format': 'distanciel',
                'duration': '4 jours',
                'description': 'Préparation certification AWS ML Specialty : SageMaker, Bedrock, data engineering AWS, déploiement et monitoring cloud ML.',
            },
            # === LLM renforcé ===
            {
                'name': 'LLM Open Source : Mistral, Llama & déploiement souverain',
                'provider': 'OCTO Academy',
                'price': '3 200€',
                'sector': '',
                'training_type': 'courte',
                'format': 'distanciel',
                'duration': '3 jours',
                'description': 'Déployer des LLM open source (Mistral, Llama) on-premise : fine-tuning, quantization, vLLM, TGI et souveraineté des données.',
            },
            {
                'name': 'Applications LLM en entreprise : chatbots, RAG & automatisation',
                'provider': 'Sia Partners Academy',
                'price': '3 800€',
                'sector': '',
                'training_type': 'courte',
                'format': 'hybride',
                'duration': '4 jours',
                'description': 'Concevoir des applications LLM pour l\'entreprise : chatbots, RAG, automatisation documentaire, prompt engineering et évaluation.',
            },
        ]

        created = 0
        for f in formations:
            _, was_created = FormationCatalog.objects.get_or_create(
                name=f['name'],
                provider=f['provider'],
                defaults={
                    'price': f['price'],
                    'sector': f['sector'],
                    'training_type': f['training_type'],
                    'format': f['format'],
                    'duration': f['duration'],
                    'description': f['description'],
                }
            )
            if was_created:
                created += 1

        self.stdout.write(f"  {created} formations de référence générées.")
