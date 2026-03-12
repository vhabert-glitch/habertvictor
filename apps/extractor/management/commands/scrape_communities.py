"""
Management command : scraping des communautés en ligne pour détecter
les tendances IA et besoins en formation.
Sources : Reddit, Hacker News, Stack Overflow.
"""
import logging
from datetime import datetime
from urllib.parse import quote_plus
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.extractor.models import CommunityPost
from apps.extractor.classifier import (
    classify_training_type, classify_sector,
    compute_relevance_score, extract_skills,
)

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'IAFormationRadar/1.0 (research; contact@ia-radar.fr)',
}

# Subreddits pertinents
SUBREDDITS = [
    'MachineLearning',
    'datascience',
    'artificial',
    'learnmachinelearning',
    'deeplearning',
    'LanguageTechnology',
    'MLOps',
    'france',           # pour le contexte français
    'FrenchTech',
]

# Mots-clés de filtrage IA
IA_FILTER_KEYWORDS = [
    'ai', 'ia', 'machine learning', 'deep learning', 'neural',
    'nlp', 'llm', 'gpt', 'training', 'formation', 'skill',
    'data science', 'computer vision', 'mlops', 'transformer',
    'artificial intelligence', 'compétences', 'learn',
    'career', 'hiring', 'formation', 'certification',
]


class Command(BaseCommand):
    help = 'Scrape Reddit, Hacker News et Stack Overflow pour les tendances IA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source', type=str, default='all',
            help='Source : reddit, hackernews, stackoverflow, all'
        )
        parser.add_argument('--limit', type=int, default=50, help='Posts max par source')

    def handle(self, *args, **options):
        source = options['source']
        limit = options['limit']
        total = 0

        scrapers = {
            'reddit': self._scrape_reddit,
            'hackernews': self._scrape_hackernews,
            'stackoverflow': self._scrape_stackoverflow,
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

        self.stdout.write(self.style.SUCCESS(f'\nTotal : {total} posts communautaires traités.'))

    # ─── REDDIT ──────────────────────────────────────────────────────────

    def _scrape_reddit(self, limit):
        """
        Scrape Reddit via l'API JSON publique (pas besoin d'auth pour .json).
        """
        count = 0
        for subreddit in SUBREDDITS:
            try:
                # Reddit JSON API (publique, pas besoin d'OAuth pour la lecture)
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={min(limit, 100)}"
                resp = requests.get(url, headers=HEADERS, timeout=15)

                if resp.status_code == 429:
                    self.stdout.write(self.style.WARNING(f"  r/{subreddit}: rate limited, skip"))
                    continue
                if resp.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"  r/{subreddit}: HTTP {resp.status_code}"))
                    continue

                data = resp.json()
                posts = data.get('data', {}).get('children', [])

                for post_data in posts:
                    post = post_data.get('data', {})
                    title = post.get('title', '')
                    selftext = post.get('selftext', '')
                    full_text = f"{title} {selftext}"

                    # Filtrer : garder seulement les posts liés à l'IA
                    if subreddit not in ('france', 'FrenchTech'):
                        # Pour les subreddits IA, on garde tout
                        pass
                    else:
                        # Pour r/france etc., filtrer par mots-clés IA
                        if not any(kw in full_text.lower() for kw in IA_FILTER_KEYWORDS):
                            continue

                    permalink = post.get('permalink', '')
                    post_url = f"https://www.reddit.com{permalink}" if permalink else ''

                    created_utc = post.get('created_utc')
                    published = None
                    if created_utc:
                        published = timezone.make_aware(
                            datetime.utcfromtimestamp(created_utc)
                        )

                    _, created = CommunityPost.objects.update_or_create(
                        url=post_url,
                        defaults={
                            'platform': 'reddit',
                            'title': title[:500],
                            'content_summary': selftext[:1000] if selftext else title,
                            'subreddit': f"r/{subreddit}",
                            'score': post.get('score', 0),
                            'comments_count': post.get('num_comments', 0),
                            'skills_mentioned': extract_skills(full_text),
                            'sector': classify_sector(full_text),
                            'training_type_match': classify_training_type(full_text),
                            'relevance_score': compute_relevance_score(full_text),
                            'published_at': published,
                        }
                    )
                    if created:
                        count += 1

                self.stdout.write(f"  r/{subreddit}: {len(posts)} posts analysés")
            except Exception as e:
                logger.error(f"Reddit r/{subreddit}: {e}")
                self.stdout.write(self.style.WARNING(f"  r/{subreddit}: erreur ({e})"))

        return count

    # ─── HACKER NEWS ─────────────────────────────────────────────────────

    def _scrape_hackernews(self, limit):
        """
        Scrape Hacker News via l'API officielle (gratuite, pas de rate limit strict).
        Utilise les endpoints : topstories, beststories, askstories.
        """
        count = 0
        endpoints = ['topstories', 'beststories', 'newstories']

        for endpoint in endpoints:
            try:
                # Récupérer les IDs des stories
                ids_resp = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/{endpoint}.json",
                    timeout=15
                )
                if ids_resp.status_code != 200:
                    continue

                story_ids = ids_resp.json()[:limit]

                for story_id in story_ids:
                    try:
                        item_resp = requests.get(
                            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                            timeout=10
                        )
                        if item_resp.status_code != 200:
                            continue

                        item = item_resp.json()
                        if not item or item.get('type') != 'story':
                            continue

                        title = item.get('title', '')
                        text = item.get('text', '')
                        full_text = f"{title} {text}"

                        # Filtrer : garder seulement les posts liés à l'IA
                        if not any(kw in full_text.lower() for kw in IA_FILTER_KEYWORDS):
                            continue

                        hn_url = f"https://news.ycombinator.com/item?id={story_id}"
                        external_url = item.get('url', hn_url)

                        published = None
                        if item.get('time'):
                            published = timezone.make_aware(
                                datetime.utcfromtimestamp(item['time'])
                            )

                        _, created = CommunityPost.objects.update_or_create(
                            url=hn_url,
                            defaults={
                                'platform': 'hackernews',
                                'title': title[:500],
                                'content_summary': text[:1000] if text else f"Lien: {external_url}",
                                'subreddit': endpoint,
                                'score': item.get('score', 0),
                                'comments_count': len(item.get('kids', [])),
                                'skills_mentioned': extract_skills(full_text),
                                'sector': classify_sector(full_text),
                                'training_type_match': classify_training_type(full_text),
                                'relevance_score': compute_relevance_score(full_text),
                                'published_at': published,
                            }
                        )
                        if created:
                            count += 1

                    except Exception as e:
                        logger.error(f"HN item {story_id}: {e}")

                self.stdout.write(f"  HN /{endpoint}: {len(story_ids)} stories analysées")
            except Exception as e:
                logger.error(f"HN {endpoint}: {e}")

        return count

    # ─── STACK OVERFLOW ──────────────────────────────────────────────────

    def _scrape_stackoverflow(self, limit):
        """
        Scrape Stack Overflow via l'API v2 (gratuite, 300 req/jour sans clé).
        Focus sur les tags IA/ML les plus populaires.
        """
        count = 0
        tags_to_search = [
            'machine-learning', 'deep-learning', 'artificial-intelligence',
            'nlp', 'pytorch', 'tensorflow', 'computer-vision',
            'llm', 'transformers', 'data-science',
        ]

        for tag in tags_to_search:
            try:
                url = (
                    f"https://api.stackexchange.com/2.3/questions"
                    f"?order=desc&sort=activity&tagged={tag}"
                    f"&site=stackoverflow&pagesize={min(limit, 100)}"
                    f"&filter=withbody"
                )
                resp = requests.get(url, timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                for q in data.get('items', []):
                    title = q.get('title', '')
                    body = q.get('body', '')
                    # Nettoyer le HTML du body
                    from bs4 import BeautifulSoup as BS
                    clean_body = BS(body, 'html.parser').get_text()[:1000] if body else ''
                    full_text = f"{title} {clean_body}"

                    q_url = q.get('link', '')
                    published = None
                    if q.get('creation_date'):
                        published = timezone.make_aware(
                            datetime.utcfromtimestamp(q['creation_date'])
                        )

                    so_tags = q.get('tags', [])

                    _, created = CommunityPost.objects.update_or_create(
                        url=q_url,
                        defaults={
                            'platform': 'stackoverflow',
                            'title': title[:500],
                            'content_summary': clean_body[:1000],
                            'subreddit': f"tags: {', '.join(so_tags[:5])}",
                            'score': q.get('score', 0),
                            'comments_count': q.get('answer_count', 0),
                            'skills_mentioned': extract_skills(full_text) + so_tags[:10],
                            'sector': classify_sector(full_text),
                            'training_type_match': classify_training_type(full_text),
                            'relevance_score': compute_relevance_score(full_text),
                            'published_at': published,
                        }
                    )
                    if created:
                        count += 1

                self.stdout.write(f"  SO [{tag}]: {len(data.get('items', []))} questions")

                # Respecter le rate limit SO
                if data.get('quota_remaining', 999) < 10:
                    self.stdout.write(self.style.WARNING("  SO: quota presque épuisé, arrêt"))
                    break

            except Exception as e:
                logger.error(f"SO [{tag}]: {e}")

        return count
