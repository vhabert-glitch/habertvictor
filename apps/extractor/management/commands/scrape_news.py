"""
Management command : extraction d'actualités IA via flux RSS.
"""
import logging
from datetime import datetime
from time import mktime
import feedparser
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.extractor.models import NewsArticle
from apps.extractor.classifier import (
    classify_sectors_multi, compute_relevance_score,
)

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    # ─── Presse tech française ───
    {
        'name': 'L\'Usine Digitale',
        'url': 'https://www.usine-digitale.fr/rss',
    },
    {
        'name': 'Le Monde Informatique',
        'url': 'https://www.lemondeinformatique.fr/flux-rss/thematique/intelligence-artificielle/rss.xml',
    },
    {
        'name': 'ActuIA',
        'url': 'https://www.actuia.com/feed/',
    },
    {
        'name': 'Journal du Net',
        'url': 'https://www.journaldunet.com/rss/',
    },
    {
        'name': 'Silicon.fr',
        'url': 'https://www.silicon.fr/feed',
    },
    {
        'name': '01net',
        'url': 'https://www.01net.com/rss/info/flux-rss/flux-toutes-les-actualites/',
    },
    {
        'name': 'ZDNet France',
        'url': 'https://www.zdnet.fr/feeds/rss/actualites/',
    },
    {
        'name': 'Les Echos Tech',
        'url': 'https://www.lesechos.fr/rss/tech-medias.xml',
    },
    {
        'name': 'La Tribune',
        'url': 'https://www.latribune.fr/feed.xml',
    },
    # ─── Presse tech internationale ───
    {
        'name': 'MIT Technology Review',
        'url': 'https://www.technologyreview.com/feed/',
    },
    {
        'name': 'VentureBeat AI',
        'url': 'https://venturebeat.com/category/ai/feed/',
    },
    {
        'name': 'The Verge AI',
        'url': 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml',
    },
    {
        'name': 'Ars Technica AI',
        'url': 'https://feeds.arstechnica.com/arstechnica/technology-lab',
    },
    {
        'name': 'TechCrunch AI',
        'url': 'https://techcrunch.com/category/artificial-intelligence/feed/',
    },
    # ─── Sources institutionnelles ───
    {
        'name': 'INR (Institut du Numérique Responsable)',
        'url': 'https://institutnr.org/feed',
    },
    {
        'name': 'CNIL',
        'url': 'https://www.cnil.fr/fr/rss.xml',
    },
    {
        'name': 'France Stratégie',
        'url': 'https://www.strategie.gouv.fr/rss.xml',
    },
    {
        'name': 'Bpifrance',
        'url': 'https://www.bpifrance.fr/rss',
    },
    {
        'name': 'Inria',
        'url': 'https://www.inria.fr/fr/feed',
    },
    {
        'name': 'CNRS',
        'url': 'https://www.cnrs.fr/fr/RSS',
    },
    # ─── Sources recherche & éducation ───
    {
        'name': 'arXiv AI (cs.AI)',
        'url': 'https://rss.arxiv.org/rss/cs.AI',
    },
    {
        'name': 'arXiv ML (cs.LG)',
        'url': 'https://rss.arxiv.org/rss/cs.LG',
    },
    {
        'name': 'Google AI Blog',
        'url': 'https://blog.google/technology/ai/rss/',
    },
    {
        'name': 'OpenAI Blog',
        'url': 'https://openai.com/blog/rss/',
    },
    {
        'name': 'Hugging Face Blog',
        'url': 'https://huggingface.co/blog/feed.xml',
    },
    # ─── Énergie & Nucléaire ───
    {
        'name': 'Connaissance des Énergies',
        'url': 'https://www.connaissancedesenergies.org/rss.xml',
    },
    {
        'name': 'L\'Usine Nouvelle - Énergie',
        'url': 'https://www.usinenouvelle.com/rss/energie.xml',
    },
    {
        'name': 'Techniques de l\'Ingénieur - Énergie',
        'url': 'https://www.techniques-ingenieur.fr/actualite/rss/',
    },
    {
        'name': 'Actu-Environnement',
        'url': 'https://www.actu-environnement.com/flux/rss/',
    },
    {
        'name': 'Enerzine',
        'url': 'https://www.enerzine.com/feed',
    },
    {
        'name': 'SFEN (Société Française d\'Énergie Nucléaire)',
        'url': 'https://www.sfen.org/feed/',
    },
    # ─── Formation, enseignement supérieur & EdTech ───
    # Les 29 flux précédents couvrent l'IA, la tech et l'industrie, mais aucun
    # ne parle de formation ni d'enseignement supérieur — soit précisément le
    # métier de NEXUS. Ces flux comblent ce trou : lancements de programmes,
    # mouvements des écoles et de l'executive education, acteurs EdTech.
    {
        'name': 'L\'Étudiant EducPros (enseignement supérieur)',
        'url': 'https://www.letudiant.fr/educpros/rss.xml',
    },
    {
        'name': 'Focus RH (formation & compétences)',
        'url': 'https://www.focusrh.com/rss.xml',
    },
    {
        'name': 'EdTech Actu',
        'url': 'https://edtechactu.com/feed/',
    },
    {
        'name': 'Le Monde Campus',
        'url': 'https://www.lemonde.fr/campus/rss_full.xml',
    },
    {
        'name': 'Courrier Cadres (management & executive education)',
        'url': 'https://courriercadres.com/feed/',
    },
    # ─── Blogs formation & emploi ───
    {
        'name': 'Blog du Modérateur',
        'url': 'https://www.blogdumoderateur.com/feed/',
    },
    {
        'name': 'Maddyness',
        'url': 'https://www.maddyness.com/feed/',
    },
    {
        'name': 'FrenchWeb',
        'url': 'https://www.frenchweb.fr/feed',
    },
]

IA_KEYWORDS = [
    'intelligence artificielle', ' ia ', ' ai ', 'machine learning',
    'deep learning', 'chatgpt', 'llm', 'ia générative', 'genai',
    'data science', 'formation ia', 'compétences ia',
    'ai act', 'éthique ia', 'artificial intelligence',
    'neural network', 'réseau de neurones', 'nlp',
    'computer vision', 'mlops', 'transformer',
    'gpt-4', 'gpt-5', 'claude', 'gemini', 'mistral',
    'hugging face', 'pytorch', 'tensorflow',
    'prompt engineering', 'rag', 'fine-tuning',
    'data engineer', 'données massives', 'big data',
    'automatisation', 'robotique', 'robot',
    'souveraineté numérique', 'cloud souverain',
    'nucléaire', 'smart grid', 'maintenance prédictive',
    'jumeau numérique', 'digital twin',
    'transition énergétique', 'décarbonation',
]


class Command(BaseCommand):
    help = 'Scrape les actualités IA via flux RSS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=20,
            help='Nombre max d\'articles par flux'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        total = 0

        for feed_info in RSS_FEEDS:
            count = self._process_feed(feed_info, limit)
            total += count

        if total == 0:
            self._generate_sample_news()

        self.stdout.write(self.style.SUCCESS(f'{total} articles traités.'))

    def _process_feed(self, feed_info, limit):
        count = 0
        try:
            feed = feedparser.parse(feed_info['url'])
            for entry in feed.entries[:limit]:
                title = entry.get('title', '')
                summary = entry.get('summary', entry.get('description', ''))
                link = entry.get('link', '')
                full_text = f"{title} {summary}"

                # Filter: only keep IA-related articles
                if not any(kw in full_text.lower() for kw in IA_KEYWORDS):
                    continue

                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = timezone.make_aware(
                        datetime.fromtimestamp(mktime(entry.published_parsed))
                    )

                _, created = NewsArticle.objects.update_or_create(
                    url=link,
                    defaults={
                        'title': title[:500],
                        'source': feed_info['name'],
                        'summary': summary[:2000],
                        'sectors': classify_sectors_multi(full_text),
                        'issues': [],
                        'published_at': published,
                        'relevance_score': compute_relevance_score(full_text),
                    }
                )
                if created:
                    count += 1

            self.stdout.write(f"  {feed_info['name']}: {count} nouveaux articles")
        except Exception as e:
            logger.error(f"Erreur flux RSS {feed_info['name']}: {e}")
            self.stdout.write(self.style.WARNING(f"  {feed_info['name']}: erreur ({e})"))

        return count

    def _generate_sample_news(self):
        """Génère des articles d'exemple si les flux RSS ne sont pas accessibles."""
        sample_articles = [
            {
                'title': 'L\'AI Act entre en vigueur : ce que les entreprises françaises doivent savoir',
                'url': 'https://example.com/ai-act-france',
                'source': 'Exemple',
                'summary': 'Le règlement européen sur l\'intelligence artificielle impose de nouvelles obligations de conformité aux entreprises. Formation et certification deviennent essentielles.',
                'sectors': ['finance', 'sante', 'industrie'],
                'issues': ['reglementation', 'ethique'],
                'relevance_score': 0.9,
            },
            {
                'title': 'Pénurie de data scientists : les formations IA en forte demande',
                'url': 'https://example.com/penurie-data-scientists',
                'source': 'Exemple',
                'summary': 'Les entreprises peinent à recruter des profils data science et machine learning. La formation interne devient un levier stratégique.',
                'sectors': ['finance', 'retail'],
                'issues': ['competences'],
                'relevance_score': 0.85,
            },
            {
                'title': 'IA générative dans la santé : opportunités et défis éthiques',
                'url': 'https://example.com/ia-generative-sante',
                'source': 'Exemple',
                'summary': 'L\'utilisation des LLM dans le secteur médical soulève des questions de fiabilité et d\'éthique. Les professionnels de santé ont besoin de formation spécifique.',
                'sectors': ['sante'],
                'issues': ['ethique', 'competences'],
                'relevance_score': 0.88,
            },
        ]
        for article in sample_articles:
            NewsArticle.objects.get_or_create(
                url=article['url'],
                defaults={**article, 'published_at': timezone.now()}
            )
        self.stdout.write(f"  {len(sample_articles)} articles d'exemple générés.")
