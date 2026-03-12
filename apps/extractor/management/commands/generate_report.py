"""
Management command : génère un rapport d'analyse IA à partir des données collectées.
Utilise l'API Claude pour l'analyse. Fonctionne aussi sans API (stats brutes).
"""
import json
from collections import Counter
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.extractor.models import (
    JobPosting, NewsArticle, CommunityPost,
    SocialSignal, TrendData, AIReport,
)
from apps.survey.models import SurveyResponse, TrainingNeed
from apps.extractor.ai_analyzer import analyze_trends, generate_weekly_report
from data.reference import SECTORS, TRAINING_TYPES


class Command(BaseCommand):
    help = 'Génère un rapport d\'analyse IA des données collectées'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=7,
            help='Période d\'analyse en jours (défaut: 7)'
        )
        parser.add_argument(
            '--no-ai', action='store_true',
            help='Générer le rapport sans appeler l\'API Claude'
        )

    def handle(self, *args, **options):
        days = options['days']
        use_ai = not options['no_ai']
        since = timezone.now() - timedelta(days=days)

        self.stdout.write(self.style.NOTICE(
            f"\nGénération du rapport — derniers {days} jours\n"
        ))

        # Collecter les stats
        stats = self._collect_stats(since)
        self._print_stats(stats)

        # Générer le rapport
        if use_ai:
            self.stdout.write(self.style.NOTICE('\nAppel API Claude pour analyse...'))
            report_content = generate_weekly_report(stats)
            if report_content:
                report = AIReport.objects.create(
                    report_type='weekly',
                    title=f"Rapport hebdomadaire — {timezone.now().strftime('%d/%m/%Y')}",
                    content=report_content,
                    data_snapshot=stats,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'\nRapport IA généré (ID: {report.id})\n'
                ))
                self.stdout.write(report_content)
            else:
                self.stdout.write(self.style.WARNING(
                    '\nImpossible de générer le rapport IA. '
                    'Vérifiez ANTHROPIC_API_KEY. Rapport stats brutes ci-dessus.'
                ))
                self._save_raw_report(stats)
        else:
            self._save_raw_report(stats)

    def _collect_stats(self, since):
        """Collecte toutes les statistiques de la période."""
        # Offres d'emploi
        jobs = JobPosting.objects.filter(extracted_at__gte=since)
        job_skills = Counter()
        job_sectors = Counter()
        job_sources = Counter()
        for job in jobs:
            for skill in job.skills:
                job_skills[skill] += 1
            if job.sector:
                job_sectors[job.sector] += 1
            job_sources[job.source] += 1

        # Articles
        articles = NewsArticle.objects.filter(extracted_at__gte=since)
        article_sources = Counter(articles.values_list('source', flat=True))

        # Communautés
        posts = CommunityPost.objects.filter(extracted_at__gte=since)
        post_platforms = Counter(posts.values_list('platform', flat=True))
        post_skills = Counter()
        for post in posts:
            for skill in post.skills_mentioned:
                post_skills[skill] += 1
        top_posts = list(
            posts.order_by('-score')[:10].values('title', 'platform', 'score', 'url')
        )

        # Signaux sociaux
        signals = SocialSignal.objects.filter(detected_at__gte=since)
        signal_sentiments = Counter(signals.values_list('sentiment', flat=True))

        # Tendances GitHub
        github_trends = list(
            TrendData.objects.filter(
                source='github', extracted_at__gte=since
            ).order_by('-value')[:10].values('keyword', 'value', 'metadata')
        )

        # Survey
        new_responses = SurveyResponse.objects.filter(
            submitted_at__gte=since, is_complete=True
        ).count()
        total_responses = SurveyResponse.objects.filter(is_complete=True).count()

        # Top training needs
        training_counts = Counter()
        for need in TrainingNeed.objects.exclude(need_level='none'):
            training_counts[need.training_type] += 1

        sector_labels = dict(SECTORS)
        training_labels = dict(TRAINING_TYPES)

        return {
            'periode_jours': (timezone.now() - since).days,
            'offres_emploi': {
                'total': jobs.count(),
                'top_competences': dict(job_skills.most_common(10)),
                'par_secteur': {sector_labels.get(k, k): v for k, v in job_sectors.most_common(8)},
                'par_source': dict(job_sources.most_common()),
            },
            'articles': {
                'total': articles.count(),
                'par_source': dict(article_sources.most_common(10)),
            },
            'communautes': {
                'total': posts.count(),
                'par_plateforme': dict(post_platforms),
                'top_competences': dict(post_skills.most_common(10)),
                'top_posts': top_posts,
            },
            'signaux_sociaux': {
                'total': signals.count(),
                'sentiments': dict(signal_sentiments),
            },
            'github_trending': github_trends,
            'questionnaire': {
                'nouvelles_reponses': new_responses,
                'total_reponses': total_responses,
                'top_formations': {
                    training_labels.get(k, k): v
                    for k, v in training_counts.most_common(5)
                },
            },
        }

    def _print_stats(self, stats):
        """Affiche les stats en console."""
        self.stdout.write(f"\n{'─'*50}")
        self.stdout.write(f"  STATISTIQUES — derniers {stats['periode_jours']} jours")
        self.stdout.write(f"{'─'*50}")

        self.stdout.write(f"\n  Offres d'emploi : {stats['offres_emploi']['total']}")
        for src, cnt in stats['offres_emploi']['par_source'].items():
            self.stdout.write(f"    • {src}: {cnt}")

        self.stdout.write(f"\n  Articles : {stats['articles']['total']}")
        self.stdout.write(f"  Posts communautaires : {stats['communautes']['total']}")

        if stats['communautes']['top_competences']:
            self.stdout.write(f"\n  Top compétences (communautés) :")
            for skill, cnt in list(stats['communautes']['top_competences'].items())[:5]:
                self.stdout.write(f"    • {skill}: {cnt} mentions")

        if stats['offres_emploi']['top_competences']:
            self.stdout.write(f"\n  Top compétences (offres) :")
            for skill, cnt in list(stats['offres_emploi']['top_competences'].items())[:5]:
                self.stdout.write(f"    • {skill}: {cnt} mentions")

        self.stdout.write(f"\n  Questionnaire :")
        self.stdout.write(f"    • Nouvelles réponses : {stats['questionnaire']['nouvelles_reponses']}")
        self.stdout.write(f"    • Total : {stats['questionnaire']['total_reponses']}")
        self.stdout.write(f"{'─'*50}\n")

    def _save_raw_report(self, stats):
        """Sauvegarde un rapport brut (sans analyse IA)."""
        lines = [
            f"# Rapport hebdomadaire — {timezone.now().strftime('%d/%m/%Y')}",
            "",
            "## Résumé",
            f"- **{stats['offres_emploi']['total']}** offres d'emploi collectées",
            f"- **{stats['articles']['total']}** articles d'actualité",
            f"- **{stats['communautes']['total']}** posts communautaires (Reddit, HN, SO)",
            f"- **{stats['questionnaire']['nouvelles_reponses']}** nouvelles réponses au questionnaire",
            "",
            "## Top compétences demandées (offres d'emploi)",
        ]
        for skill, cnt in list(stats['offres_emploi']['top_competences'].items())[:10]:
            lines.append(f"- {skill}: {cnt} mentions")

        lines.extend(["", "## Top compétences (communautés)"])
        for skill, cnt in list(stats['communautes']['top_competences'].items())[:10]:
            lines.append(f"- {skill}: {cnt} mentions")

        if stats['questionnaire']['top_formations']:
            lines.extend(["", "## Formations les plus demandées (questionnaire)"])
            for formation, cnt in stats['questionnaire']['top_formations'].items():
                lines.append(f"- {formation}: {cnt}")

        content = "\n".join(lines)
        report = AIReport.objects.create(
            report_type='weekly',
            title=f"Rapport stats — {timezone.now().strftime('%d/%m/%Y')}",
            content=content,
            data_snapshot=stats,
        )
        self.stdout.write(self.style.SUCCESS(f'Rapport stats sauvegardé (ID: {report.id})'))
