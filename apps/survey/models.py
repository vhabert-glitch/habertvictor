import uuid
from django.db import models
from data.reference import (
    SECTORS, COMPANY_SIZES, AI_MATURITY_LEVELS,
    TRAINING_TYPES, NEED_LEVELS, URGENCY_LEVELS,
    FORMAT_CHOICES, BUDGET_RANGES, CRITICAL_ISSUES,
)


class Company(models.Model):
    name = models.CharField('Nom de l\'entreprise', max_length=255)
    sector = models.CharField('Secteur d\'activité', max_length=50, choices=SECTORS)
    size = models.CharField('Taille', max_length=10, choices=COMPANY_SIZES)
    location = models.CharField('Localisation', max_length=255)
    email = models.EmailField('Email de contact')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Entreprise'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class SurveyResponse(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='responses')
    share_token = models.UUIDField(default=uuid.uuid4, unique=True)

    # Maturité IA
    ai_maturity = models.CharField(
        'Niveau de maturité IA', max_length=20,
        choices=AI_MATURITY_LEVELS, blank=True
    )
    ai_tools = models.TextField('Outils IA utilisés', blank=True)
    trained_employees = models.PositiveIntegerField(
        'Nombre de collaborateurs formés', default=0
    )

    # Préférences formation
    budget = models.CharField(
        'Budget formation IA', max_length=20,
        choices=BUDGET_RANGES, blank=True
    )
    preferred_format = models.CharField(
        'Format préféré', max_length=20,
        choices=FORMAT_CHOICES, blank=True
    )
    priority_skills = models.JSONField(
        'Compétences prioritaires', default=list, blank=True
    )

    # Champ libre
    free_text = models.TextField('Besoins spécifiques non couverts', blank=True)

    # Statut
    is_complete = models.BooleanField(default=False)
    current_step = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réponse au questionnaire'
        ordering = ['-created_at']

    def __str__(self):
        status = "Complète" if self.is_complete else f"Étape {self.current_step}/4"
        return f"{self.company.name} — {status}"


class TrainingNeed(models.Model):
    response = models.ForeignKey(
        SurveyResponse, on_delete=models.CASCADE, related_name='training_needs'
    )
    training_type = models.CharField(
        'Type de formation', max_length=30, choices=TRAINING_TYPES
    )
    need_level = models.CharField(
        'Niveau de besoin', max_length=10, choices=NEED_LEVELS, default='none'
    )
    people_count = models.PositiveIntegerField('Nombre de personnes à former', default=0)
    urgency = models.CharField(
        'Urgence', max_length=15, choices=URGENCY_LEVELS, blank=True
    )

    class Meta:
        verbose_name = 'Besoin en formation'
        unique_together = ('response', 'training_type')

    def __str__(self):
        return f"{self.get_training_type_display()} — {self.get_need_level_display()}"


class CriticalIssueRanking(models.Model):
    response = models.ForeignKey(
        SurveyResponse, on_delete=models.CASCADE, related_name='issue_rankings'
    )
    issue_type = models.CharField(
        'Enjeu', max_length=30, choices=CRITICAL_ISSUES
    )
    rank = models.PositiveIntegerField('Classement (1 = plus prioritaire)')

    class Meta:
        verbose_name = 'Classement des enjeux'
        unique_together = ('response', 'issue_type')
        ordering = ['rank']

    def __str__(self):
        return f"#{self.rank} — {self.get_issue_type_display()}"
