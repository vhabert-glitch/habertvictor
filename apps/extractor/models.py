from django.db import models
from data.reference import SECTORS, TRAINING_TYPES, CRITICAL_ISSUES


class JobPosting(models.Model):
    title = models.CharField('Titre du poste', max_length=500)
    source = models.CharField('Source', max_length=100)
    url = models.URLField('Lien', max_length=1000, blank=True)
    sector = models.CharField('Secteur', max_length=50, choices=SECTORS, blank=True)
    skills = models.JSONField('Compétences détectées', default=list)
    location = models.CharField('Localisation', max_length=255, blank=True)
    training_type_match = models.CharField(
        'Type de formation associé', max_length=30,
        choices=TRAINING_TYPES, blank=True
    )
    raw_description = models.TextField('Description brute', blank=True)
    relevance_score = models.FloatField('Score de pertinence', default=0.0)
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Offre d\'emploi'
        verbose_name_plural = 'Offres d\'emploi'
        ordering = ['-extracted_at']

    def __str__(self):
        return f"{self.title} ({self.source})"


class NewsArticle(models.Model):
    title = models.CharField('Titre', max_length=500)
    url = models.URLField('Lien', max_length=1000, unique=True)
    source = models.CharField('Source', max_length=200)
    summary = models.TextField('Résumé', blank=True)
    sectors = models.JSONField('Secteurs concernés', default=list)
    issues = models.JSONField('Enjeux concernés', default=list)
    published_at = models.DateTimeField('Date de publication', null=True, blank=True)
    relevance_score = models.FloatField('Score de pertinence', default=0.0)
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Article d\'actualité'
        verbose_name_plural = 'Articles d\'actualité'
        ordering = ['-published_at']

    def __str__(self):
        return self.title


class CommunityPost(models.Model):
    """Posts et discussions issus de forums et communautés (Reddit, HN, SO, forums)."""
    PLATFORM_CHOICES = [
        ('reddit', 'Reddit'),
        ('hackernews', 'Hacker News'),
        ('stackoverflow', 'Stack Overflow'),
        ('forum', 'Forum spécialisé'),
        ('other', 'Autre'),
    ]

    platform = models.CharField('Plateforme', max_length=20, choices=PLATFORM_CHOICES)
    title = models.CharField('Titre', max_length=500)
    url = models.URLField('Lien', max_length=1000, unique=True)
    content_summary = models.TextField('Résumé', blank=True)
    subreddit = models.CharField('Subreddit / catégorie', max_length=100, blank=True)
    score = models.IntegerField('Score / upvotes', default=0)
    comments_count = models.IntegerField('Nombre de commentaires', default=0)
    skills_mentioned = models.JSONField('Compétences mentionnées', default=list)
    sector = models.CharField('Secteur', max_length=50, choices=SECTORS, blank=True)
    training_type_match = models.CharField(
        'Type de formation associé', max_length=30,
        choices=TRAINING_TYPES, blank=True
    )
    relevance_score = models.FloatField('Score de pertinence', default=0.0)
    published_at = models.DateTimeField('Date de publication', null=True, blank=True)
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Post communautaire'
        verbose_name_plural = 'Posts communautaires'
        ordering = ['-published_at']

    def __str__(self):
        return f"[{self.get_platform_display()}] {self.title[:80]}"


class TrendData(models.Model):
    """Données de tendances (Google Trends, GitHub trending, etc.)."""
    SOURCE_CHOICES = [
        ('google_trends', 'Google Trends'),
        ('github', 'GitHub Trending'),
        ('pypi', 'PyPI Downloads'),
        ('other', 'Autre'),
    ]

    source = models.CharField('Source', max_length=20, choices=SOURCE_CHOICES)
    keyword = models.CharField('Mot-clé / terme', max_length=200)
    value = models.FloatField('Valeur (score / count)', default=0.0)
    region = models.CharField('Région', max_length=50, default='FR')
    category = models.CharField('Catégorie', max_length=100, blank=True)
    metadata = models.JSONField('Métadonnées', default=dict, blank=True)
    measured_at = models.DateTimeField('Date de mesure')
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Donnée de tendance'
        verbose_name_plural = 'Données de tendances'
        ordering = ['-measured_at']

    def __str__(self):
        return f"[{self.get_source_display()}] {self.keyword}: {self.value}"


class SocialSignal(models.Model):
    PLATFORM_CHOICES = [
        ('linkedin', 'LinkedIn'),
        ('twitter', 'X (Twitter)'),
        ('reddit', 'Reddit'),
        ('hackernews', 'Hacker News'),
        ('other', 'Autre'),
    ]
    SENTIMENT_CHOICES = [
        ('positive', 'Positif'),
        ('neutral', 'Neutre'),
        ('negative', 'Négatif'),
    ]

    platform = models.CharField('Plateforme', max_length=20, choices=PLATFORM_CHOICES)
    content_summary = models.TextField('Résumé du contenu')
    url = models.URLField('Lien', max_length=1000, blank=True)
    hashtags = models.JSONField('Hashtags', default=list)
    sector = models.CharField('Secteur', max_length=50, choices=SECTORS, blank=True)
    sentiment = models.CharField(
        'Sentiment', max_length=10, choices=SENTIMENT_CHOICES, default='neutral'
    )
    relevance_score = models.FloatField('Score de pertinence', default=0.0)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Signal social'
        verbose_name_plural = 'Signaux sociaux'
        ordering = ['-detected_at']

    def __str__(self):
        return f"[{self.get_platform_display()}] {self.content_summary[:80]}"


class AIReport(models.Model):
    """Rapports et analyses générés automatiquement par l'IA."""
    REPORT_TYPES = [
        ('weekly', 'Rapport hebdomadaire'),
        ('trend_analysis', 'Analyse de tendances'),
        ('sector_focus', 'Focus sectoriel'),
    ]

    report_type = models.CharField('Type', max_length=20, choices=REPORT_TYPES)
    title = models.CharField('Titre', max_length=300)
    content = models.TextField('Contenu (Markdown)')
    data_snapshot = models.JSONField('Données source', default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rapport IA'
        verbose_name_plural = 'Rapports IA'
        ordering = ['-generated_at']

    def __str__(self):
        return f"[{self.get_report_type_display()}] {self.title}"
