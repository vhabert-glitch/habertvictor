"""
Generate test survey responses to populate the dashboard.
"""
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.survey.models import Company, SurveyResponse, TrainingNeed, CriticalIssueRanking
from data.reference import (
    SECTORS, COMPANY_SIZES, AI_MATURITY_LEVELS,
    TRAINING_TYPES, NEED_LEVELS, URGENCY_LEVELS,
    FORMAT_CHOICES, BUDGET_RANGES, CRITICAL_ISSUES, AI_SKILLS,
)


COMPANY_NAMES = [
    'TechVision France', 'DataMind Solutions', 'InnoSanté Paris',
    'FinAI Consulting', 'GreenEnergy Lab', 'SmartRetail Group',
    'EduTech Academy', 'LogisTech Express', 'CyberShield France',
    'AgriIA Innovations', 'BankAI Solutions', 'MediTech Lyon',
    'AutoPilot Industries', 'CloudFirst Paris', 'AI Factory Bordeaux',
]

CITIES = ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Bordeaux', 'Lille', 'Nantes', 'Strasbourg']


class Command(BaseCommand):
    help = 'Génère des données de test pour le questionnaire'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10, help='Nombre de réponses à générer')

    def handle(self, *args, **options):
        count = options['count']
        sectors = [code for code, _ in SECTORS]
        sizes = [code for code, _ in COMPANY_SIZES]
        maturities = [code for code, _ in AI_MATURITY_LEVELS]
        budgets = [code for code, _ in BUDGET_RANGES]
        formats = [code for code, _ in FORMAT_CHOICES]

        for i in range(count):
            name = random.choice(COMPANY_NAMES) + f" #{i+1}"
            company = Company.objects.create(
                name=name,
                sector=random.choice(sectors[:-1]),  # exclude 'autre'
                size=random.choice(sizes),
                location=random.choice(CITIES),
                email=f"contact{i}@example.com",
            )

            days_ago = random.randint(0, 90)
            response = SurveyResponse.objects.create(
                company=company,
                ai_maturity=random.choice(maturities),
                ai_tools=random.choice([
                    'ChatGPT, Copilot',
                    'TensorFlow, PyTorch',
                    'Aucun',
                    'Outils internes',
                    'ChatGPT',
                ]),
                trained_employees=random.randint(0, 200),
                budget=random.choice(budgets),
                preferred_format=random.choice(formats),
                priority_skills=random.sample(
                    [code for code, _ in AI_SKILLS],
                    k=random.randint(2, 6)
                ),
                is_complete=True,
                submitted_at=timezone.now() - timedelta(days=days_ago),
            )

            for t_code, _ in TRAINING_TYPES:
                need_level = random.choice([code for code, _ in NEED_LEVELS])
                TrainingNeed.objects.create(
                    response=response,
                    training_type=t_code,
                    need_level=need_level,
                    people_count=random.randint(0, 50) if need_level != 'none' else 0,
                    urgency=random.choice([code for code, _ in URGENCY_LEVELS]) if need_level != 'none' else '',
                )

            issue_codes = [code for code, _ in CRITICAL_ISSUES]
            random.shuffle(issue_codes)
            for rank, code in enumerate(issue_codes, 1):
                CriticalIssueRanking.objects.create(
                    response=response,
                    issue_type=code,
                    rank=rank,
                )

        self.stdout.write(self.style.SUCCESS(f'{count} réponses de test générées.'))
