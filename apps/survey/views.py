import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import Company, SurveyResponse, TrainingNeed, CriticalIssueRanking
from .forms import CompanyForm, MaturityForm, TrainingNeedForm, IssuesForm
from data.reference import TRAINING_TYPES, CRITICAL_ISSUES


def survey_start(request):
    """Page d'accueil du questionnaire ou reprise via token."""
    token = request.GET.get('token')
    if token:
        response = get_object_or_404(SurveyResponse, share_token=token)
        return redirect('survey:step', token=response.share_token, step=response.current_step)
    return render(request, 'survey/start.html')


def survey_create(request):
    """Crée une nouvelle réponse et redirige vers l'étape 1."""
    if request.method == 'POST':
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save()
            response = SurveyResponse.objects.create(company=company, current_step=1)
            return redirect('survey:step', token=response.share_token, step=2)
    else:
        form = CompanyForm()
    return render(request, 'survey/step1_company.html', {'form': form, 'step': 1})


def survey_step(request, token, step):
    """Gestion des étapes du questionnaire."""
    response = get_object_or_404(SurveyResponse, share_token=token)

    if response.is_complete:
        return redirect('survey:confirmation', token=token)

    if step == 1:
        return _handle_step1(request, response)
    elif step == 2:
        return _handle_step2(request, response)
    elif step == 3:
        return _handle_step3(request, response)
    elif step == 4:
        return _handle_step4(request, response)
    else:
        return redirect('survey:step', token=token, step=1)


def _handle_step1(request, response):
    if request.method == 'POST':
        form = CompanyForm(request.POST, instance=response.company)
        if form.is_valid():
            form.save()
            response.current_step = 2
            response.save()
            return redirect('survey:step', token=response.share_token, step=2)
    else:
        form = CompanyForm(instance=response.company)
    return render(request, 'survey/step1_company.html', {
        'form': form, 'step': 1, 'token': response.share_token
    })


def _handle_step2(request, response):
    if request.method == 'POST':
        form = MaturityForm(request.POST, instance=response)
        if form.is_valid():
            form.save()
            response.current_step = 3
            response.save()
            return redirect('survey:step', token=response.share_token, step=3)
    else:
        form = MaturityForm(instance=response)
    return render(request, 'survey/step2_maturity.html', {
        'form': form, 'step': 2, 'token': response.share_token
    })


def _handle_step3(request, response):
    if request.method == 'POST':
        form = TrainingNeedForm(request.POST)
        if form.is_valid():
            # Save training needs
            for code, label in TRAINING_TYPES:
                TrainingNeed.objects.update_or_create(
                    response=response,
                    training_type=code,
                    defaults={
                        'need_level': form.cleaned_data.get(f'{code}_level', 'none'),
                        'people_count': form.cleaned_data.get(f'{code}_count', 0),
                        'urgency': form.cleaned_data.get(f'{code}_urgency', ''),
                    }
                )
            response.priority_skills = form.cleaned_data.get('priority_skills', [])
            response.budget = form.cleaned_data.get('budget', '')
            response.preferred_format = form.cleaned_data.get('preferred_format', '')
            response.current_step = 4
            response.save()
            return redirect('survey:step', token=response.share_token, step=4)
    else:
        initial = {}
        for need in response.training_needs.all():
            initial[f'{need.training_type}_level'] = need.need_level
            initial[f'{need.training_type}_count'] = need.people_count
            initial[f'{need.training_type}_urgency'] = need.urgency
        initial['priority_skills'] = response.priority_skills
        initial['budget'] = response.budget
        initial['preferred_format'] = response.preferred_format
        form = TrainingNeedForm(initial=initial)
    return render(request, 'survey/step3_needs.html', {
        'form': form, 'step': 3, 'token': response.share_token,
        'training_types': TRAINING_TYPES,
    })


def _handle_step4(request, response):
    if request.method == 'POST':
        form = IssuesForm(request.POST)
        if form.is_valid():
            for code, label in CRITICAL_ISSUES:
                rank = form.cleaned_data.get(f'issue_{code}', 5)
                CriticalIssueRanking.objects.update_or_create(
                    response=response,
                    issue_type=code,
                    defaults={'rank': rank}
                )
            response.free_text = form.cleaned_data.get('free_text', '')
            response.is_complete = True
            response.submitted_at = timezone.now()
            response.current_step = 4
            response.save()

            # Send confirmation email
            send_mail(
                subject='Merci pour votre participation — IA Formation Radar',
                message=(
                    f"Bonjour,\n\n"
                    f"Nous avons bien reçu les réponses de {response.company.name} "
                    f"au questionnaire IA Formation Radar.\n\n"
                    f"Merci pour votre contribution !\n\n"
                    f"L'équipe IA Formation Radar"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[response.company.email],
                fail_silently=True,
            )

            return redirect('survey:confirmation', token=response.share_token)
    else:
        initial = {'free_text': response.free_text}
        for ranking in response.issue_rankings.all():
            initial[f'issue_{ranking.issue_type}'] = ranking.rank
        form = IssuesForm(initial=initial)
    return render(request, 'survey/step4_issues.html', {
        'form': form, 'step': 4, 'token': response.share_token,
        'issues': CRITICAL_ISSUES,
    })


def survey_confirmation(request, token):
    response = get_object_or_404(SurveyResponse, share_token=token)
    return render(request, 'survey/confirmation.html', {
        'response': response,
        'share_url': request.build_absolute_uri(f'/survey/?token={token}'),
    })


@login_required
def export_csv(request):
    """Export toutes les réponses en CSV."""
    http_response = HttpResponse(content_type='text/csv')
    http_response['Content-Disposition'] = 'attachment; filename="ia-formation-responses.csv"'
    http_response.write('\ufeff')  # BOM for Excel

    writer = csv.writer(http_response, delimiter=';')

    # Header
    header = [
        'Entreprise', 'Secteur', 'Taille', 'Localisation', 'Email',
        'Maturité IA', 'Outils IA', 'Collaborateurs formés',
        'Budget', 'Format préféré', 'Date de soumission',
    ]
    for code, label in TRAINING_TYPES:
        header.extend([f'{label} - Niveau', f'{label} - Personnes', f'{label} - Urgence'])
    for code, label in CRITICAL_ISSUES:
        header.append(f'Enjeu: {label}')
    header.append('Commentaires libres')
    writer.writerow(header)

    # Data
    for resp in SurveyResponse.objects.filter(is_complete=True).select_related('company'):
        row = [
            resp.company.name, resp.company.get_sector_display(),
            resp.company.get_size_display(), resp.company.location,
            resp.company.email, resp.get_ai_maturity_display(),
            resp.ai_tools, resp.trained_employees,
            resp.get_budget_display(), resp.get_preferred_format_display(),
            resp.submitted_at.strftime('%d/%m/%Y %H:%M') if resp.submitted_at else '',
        ]
        needs = {n.training_type: n for n in resp.training_needs.all()}
        for code, label in TRAINING_TYPES:
            need = needs.get(code)
            if need:
                row.extend([need.get_need_level_display(), need.people_count, need.get_urgency_display()])
            else:
                row.extend(['', 0, ''])
        rankings = {r.issue_type: r.rank for r in resp.issue_rankings.all()}
        for code, label in CRITICAL_ISSUES:
            row.append(rankings.get(code, ''))
        row.append(resp.free_text)
        writer.writerow(row)

    return http_response
