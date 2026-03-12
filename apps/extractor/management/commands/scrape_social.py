"""
Management command : monitoring des signaux sociaux (LinkedIn, X/Twitter).
En mode prototype, génère des données d'exemple.
Les APIs réelles nécessitent des credentials (LinkedIn API, X API v2).
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.extractor.models import SocialSignal
from apps.extractor.classifier import classify_sector, compute_relevance_score

logger = logging.getLogger(__name__)

TRACKED_HASHTAGS = [
    '#IAFormation', '#AIAct', '#CompétencesIA', '#FormationIA',
    '#MachineLearning', '#DataScience', '#IAGenerative',
    '#TransformationDigitale', '#EthiqueIA', '#MLOps',
]


class Command(BaseCommand):
    help = 'Collecte les signaux sociaux liés à l\'IA (LinkedIn, X/Twitter)'

    def handle(self, *args, **options):
        # En mode prototype, générer des données d'exemple
        # En production, implémenter les appels aux APIs LinkedIn et X
        self._generate_sample_signals()
        self.stdout.write(self.style.SUCCESS('Signaux sociaux collectés.'))

    def _generate_sample_signals(self):
        """Génère des signaux d'exemple pour le prototype."""
        sample_signals = [
            {
                'platform': 'linkedin',
                'content_summary': 'Les entreprises du CAC40 investissent massivement dans la formation IA de leurs cadres. 78% prévoient des programmes de montée en compétences d\'ici 2025.',
                'hashtags': ['#FormationIA', '#TransformationDigitale', '#CompétencesIA'],
                'sector': 'finance',
                'sentiment': 'positive',
                'relevance_score': 0.9,
            },
            {
                'platform': 'twitter',
                'content_summary': 'L\'AI Act va obliger les entreprises à former leurs équipes sur l\'IA responsable. Qui est prêt ? #AIAct #EthiqueIA',
                'hashtags': ['#AIAct', '#EthiqueIA'],
                'sector': 'administration',
                'sentiment': 'neutral',
                'relevance_score': 0.85,
            },
            {
                'platform': 'linkedin',
                'content_summary': 'Retour d\'expérience : notre hôpital a formé 200 médecins à l\'utilisation de l\'IA diagnostique. Résultats prometteurs mais le chemin est encore long.',
                'hashtags': ['#IAFormation', '#SantéNumérique'],
                'sector': 'sante',
                'sentiment': 'positive',
                'relevance_score': 0.92,
            },
            {
                'platform': 'twitter',
                'content_summary': 'Pénurie de profils MLOps en France. Les formations spécialisées sont rares et les entreprises peinent à déployer leurs modèles en production.',
                'hashtags': ['#MLOps', '#DataScience', '#Recrutement'],
                'sector': 'industrie',
                'sentiment': 'negative',
                'relevance_score': 0.88,
            },
            {
                'platform': 'linkedin',
                'content_summary': 'Notre PME dans le retail a adopté une solution d\'IA pour la prévision des stocks. Formation des équipes en 3 mois. ROI visible dès le 2e trimestre.',
                'hashtags': ['#IAGenerative', '#Retail', '#PME'],
                'sector': 'retail',
                'sentiment': 'positive',
                'relevance_score': 0.8,
            },
        ]
        for signal in sample_signals:
            SocialSignal.objects.create(**signal)
        self.stdout.write(f"  {len(sample_signals)} signaux d'exemple générés.")
