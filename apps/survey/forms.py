from django import forms
from .models import Company, SurveyResponse, TrainingNeed, CriticalIssueRanking
from data.reference import (
    SECTORS, COMPANY_SIZES, AI_MATURITY_LEVELS,
    TRAINING_TYPES, NEED_LEVELS, URGENCY_LEVELS,
    FORMAT_CHOICES, BUDGET_RANGES, CRITICAL_ISSUES, AI_SKILLS,
)


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'sector', 'size', 'location', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de l\'entreprise'}),
            'sector': forms.Select(attrs={'class': 'form-select'}),
            'size': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ville ou région'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@entreprise.com'}),
        }


class MaturityForm(forms.ModelForm):
    class Meta:
        model = SurveyResponse
        fields = ['ai_maturity', 'ai_tools', 'trained_employees']
        widgets = {
            'ai_maturity': forms.Select(attrs={'class': 'form-select'}),
            'ai_tools': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Ex: ChatGPT, Copilot, outils internes...'
            }),
            'trained_employees': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class TrainingNeedForm(forms.Form):
    """Formulaire dynamique pour les besoins de formation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for code, label in TRAINING_TYPES:
            self.fields[f'{code}_level'] = forms.ChoiceField(
                label=label,
                choices=NEED_LEVELS,
                widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
                initial='none',
            )
            self.fields[f'{code}_count'] = forms.IntegerField(
                label='Personnes',
                min_value=0, initial=0,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm', 'style': 'width:80px'
                }),
            )
            self.fields[f'{code}_urgency'] = forms.ChoiceField(
                label='Urgence',
                choices=[('', '—')] + list(URGENCY_LEVELS),
                required=False,
                widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
            )

    priority_skills = forms.MultipleChoiceField(
        label='Compétences IA prioritaires',
        choices=AI_SKILLS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )
    budget = forms.ChoiceField(
        label='Budget formation IA envisagé',
        choices=[('', 'Sélectionner')] + list(BUDGET_RANGES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    preferred_format = forms.ChoiceField(
        label='Format de formation préféré',
        choices=[('', 'Sélectionner')] + list(FORMAT_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class IssuesForm(forms.Form):
    """Formulaire pour le classement des enjeux critiques."""
    free_text = forms.CharField(
        label='Besoins spécifiques non couverts',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 4,
            'placeholder': 'Décrivez tout besoin en formation IA qui ne serait pas couvert par les options précédentes...'
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for code, label in CRITICAL_ISSUES:
            self.fields[f'issue_{code}'] = forms.IntegerField(
                label=label,
                min_value=1, max_value=10,
                initial=5,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm',
                    'style': 'width:70px', 'min': 1, 'max': 10,
                }),
            )
