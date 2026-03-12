import json
from collections import Counter, defaultdict
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, F
from django.http import JsonResponse
from apps.survey.models import SurveyResponse, TrainingNeed, CriticalIssueRanking, Company
from apps.extractor.models import JobPosting, NewsArticle, SocialSignal, CommunityPost, TrendData, AIReport
from data.reference import (
    SECTORS, TRAINING_TYPES, NEED_LEVELS,
    URGENCY_LEVELS, COMPANY_SIZES, AI_MATURITY_LEVELS,
    CRITICAL_ISSUES,
)


@login_required
def dashboard_index(request):
    """Page principale du dashboard avec KPIs et graphiques."""
    # Filtres
    sector_filter = request.GET.get('sector', '')
    size_filter = request.GET.get('size', '')
    location_filter = request.GET.get('location', '')

    responses = SurveyResponse.objects.filter(is_complete=True).select_related('company')

    if sector_filter:
        responses = responses.filter(company__sector=sector_filter)
    if size_filter:
        responses = responses.filter(company__size=size_filter)
    if location_filter:
        responses = responses.filter(company__location__icontains=location_filter)

    response_ids = responses.values_list('id', flat=True)
    training_needs = TrainingNeed.objects.filter(response_id__in=response_ids)

    # === KPIs ===
    total_responses = responses.count()

    # Secteur le plus demandeur
    sector_counts = Counter(responses.values_list('company__sector', flat=True))
    top_sector_code = sector_counts.most_common(1)[0][0] if sector_counts else ''
    top_sector = dict(SECTORS).get(top_sector_code, 'N/A')

    # Formation la plus demandée
    need_counts = Counter(
        training_needs.exclude(need_level='none').values_list('training_type', flat=True)
    )
    top_training_code = need_counts.most_common(1)[0][0] if need_counts else ''
    top_training = dict(TRAINING_TYPES).get(top_training_code, 'N/A')

    # Urgence moyenne
    urgency_map = {'3months': 1, '3_6months': 2, '6_12months': 3, '12months_plus': 4}
    urgency_values = [
        urgency_map[u] for u in
        training_needs.exclude(urgency='').values_list('urgency', flat=True)
        if u in urgency_map
    ]
    avg_urgency_num = sum(urgency_values) / len(urgency_values) if urgency_values else 0
    urgency_labels = {1: '< 3 mois', 2: '3-6 mois', 3: '6-12 mois', 4: '> 12 mois'}
    avg_urgency = urgency_labels.get(round(avg_urgency_num), 'N/A')

    # === Chart data ===
    sector_labels = dict(SECTORS)
    training_labels = dict(TRAINING_TYPES)

    # 1. Besoins par secteur (bar chart)
    needs_by_sector = {}
    for code, label in SECTORS:
        count = training_needs.filter(
            response__company__sector=code
        ).exclude(need_level='none').count()
        if count > 0:
            needs_by_sector[label] = count

    # 2. Top formations (horizontal bar)
    top_trainings = {}
    for code, label in TRAINING_TYPES:
        count = training_needs.filter(
            training_type=code
        ).exclude(need_level='none').count()
        if count > 0:
            top_trainings[label] = count
    top_trainings = dict(sorted(top_trainings.items(), key=lambda x: x[1], reverse=True))

    # 3. Heatmap data (sector x training)
    heatmap_data = []
    for s_code, s_label in SECTORS:
        if s_code == 'autre':
            continue
        row = []
        for t_code, t_label in TRAINING_TYPES:
            count = training_needs.filter(
                response__company__sector=s_code,
                training_type=t_code,
            ).exclude(need_level='none').count()
            row.append(count)
        heatmap_data.append({'sector': s_label, 'values': row})

    # 4. Evolution temporelle (line chart)
    timeline = {}
    for resp in responses.order_by('submitted_at'):
        if resp.submitted_at:
            month = resp.submitted_at.strftime('%Y-%m')
            timeline[month] = timeline.get(month, 0) + 1

    # 5. Répartition par urgence (donut)
    urgency_dist = {}
    for code, label in URGENCY_LEVELS:
        count = training_needs.filter(urgency=code).count()
        if count > 0:
            urgency_dist[label] = count

    # 6. Répartition par taille (pie)
    size_dist = {}
    for code, label in COMPANY_SIZES:
        count = responses.filter(company__size=code).count()
        if count > 0:
            size_dist[label] = count

    # 7. Budget moyen par secteur (bar)
    budget_map = {
        'less_5k': 2500, '5k_20k': 12500, '20k_50k': 35000,
        '50k_100k': 75000, '100k_plus': 150000, 'unknown': 0,
    }
    budget_by_sector = {}
    for code, label in SECTORS:
        budgets = [
            budget_map.get(b, 0) for b in
            responses.filter(company__sector=code).exclude(budget='unknown').exclude(budget='')
            .values_list('budget', flat=True)
        ]
        if budgets:
            budget_by_sector[label] = round(sum(budgets) / len(budgets))

    # 8. Maturité IA par secteur (stacked bar)
    maturity_by_sector = {}
    for s_code, s_label in SECTORS:
        if s_code == 'autre':
            continue
        dist = {}
        for m_code, m_label in AI_MATURITY_LEVELS:
            count = responses.filter(company__sector=s_code, ai_maturity=m_code).count()
            dist[m_label] = count
        if any(dist.values()):
            maturity_by_sector[s_label] = dist

    # === Données extractor ===
    recent_jobs = JobPosting.objects.order_by('-extracted_at')[:10]
    recent_news = NewsArticle.objects.order_by('-published_at')[:8]
    recent_signals = SocialSignal.objects.order_by('-detected_at')[:5]
    recent_community = CommunityPost.objects.order_by('-published_at')[:8]
    recent_trends = TrendData.objects.filter(source='github').order_by('-value')[:10]

    # Skills from job postings
    job_skills = Counter()
    for job in JobPosting.objects.all():
        for skill in job.skills:
            job_skills[skill] += 1
    top_job_skills = dict(job_skills.most_common(15))

    # Community skills
    community_skills = Counter()
    for post in CommunityPost.objects.all():
        for skill in post.skills_mentioned:
            community_skills[skill] += 1
    top_community_skills = dict(community_skills.most_common(15))

    # Job sources distribution
    job_sources = dict(Counter(
        JobPosting.objects.values_list('source', flat=True)
    ))

    # Community platforms distribution
    community_platforms = dict(Counter(
        CommunityPost.objects.values_list('platform', flat=True)
    ))

    # News sources distribution
    news_sources = dict(Counter(
        NewsArticle.objects.values_list('source', flat=True)
    ).most_common(10))

    # Extraction stats KPIs
    total_jobs = JobPosting.objects.count()
    total_news = NewsArticle.objects.count()
    total_community = CommunityPost.objects.count()
    total_signals = SocialSignal.objects.count()
    total_trends = TrendData.objects.count()

    context = {
        # KPIs
        'total_responses': total_responses,
        'top_sector': top_sector,
        'top_training': top_training,
        'avg_urgency': avg_urgency,
        # Chart data (JSON)
        'needs_by_sector': json.dumps(needs_by_sector),
        'top_trainings': json.dumps(top_trainings),
        'heatmap_data': json.dumps(heatmap_data),
        'heatmap_training_labels': json.dumps([l for _, l in TRAINING_TYPES]),
        'timeline_data': json.dumps(timeline),
        'urgency_dist': json.dumps(urgency_dist),
        'size_dist': json.dumps(size_dist),
        'budget_by_sector': json.dumps(budget_by_sector),
        'maturity_by_sector': json.dumps(maturity_by_sector),
        'maturity_levels': json.dumps([l for _, l in AI_MATURITY_LEVELS]),
        'top_job_skills': json.dumps(top_job_skills),
        'top_community_skills': json.dumps(top_community_skills),
        'job_sources': json.dumps(job_sources),
        'community_platforms': json.dumps(community_platforms),
        'news_sources': json.dumps(news_sources),
        # Extractor data
        'recent_jobs': recent_jobs,
        'recent_news': recent_news,
        'recent_signals': recent_signals,
        'recent_community': recent_community,
        'recent_trends': recent_trends,
        # Extraction stats
        'total_jobs': total_jobs,
        'total_news': total_news,
        'total_community': total_community,
        'total_signals': total_signals,
        'total_trends': total_trends,
        # Filters
        'sectors': SECTORS,
        'sizes': COMPANY_SIZES,
        'current_sector': sector_filter,
        'current_size': size_filter,
        'current_location': location_filter,
    }

    return render(request, 'dashboard/index.html', context)


@login_required
def responses_list(request):
    """Tableau des réponses entreprises."""
    responses = SurveyResponse.objects.filter(
        is_complete=True
    ).select_related('company').order_by('-submitted_at')

    return render(request, 'dashboard/responses.html', {
        'responses': responses,
    })


@login_required
def reports_list(request):
    """Liste des rapports IA générés."""
    reports = AIReport.objects.all()[:20]
    return render(request, 'dashboard/reports.html', {'reports': reports})


@login_required
def report_detail(request, report_id):
    """Détail d'un rapport IA."""
    from django.shortcuts import get_object_or_404
    report = get_object_or_404(AIReport, id=report_id)
    return render(request, 'dashboard/report_detail.html', {'report': report})
