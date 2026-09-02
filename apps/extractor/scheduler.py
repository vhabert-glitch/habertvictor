"""
Background scheduler : auto-refresh des données (jobs, news, formations).
Utilise APScheduler pour planifier les scrapes en arrière-plan.
"""
import logging
from django.core.management import call_command

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler():
    """Démarre le scheduler en background (daemon thread)."""
    global _scheduler

    if _scheduler is not None:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.warning('[Scheduler] apscheduler non installé, scheduler désactivé.')
        return

    _scheduler = BackgroundScheduler(daemon=True)

    # Jobs toutes les 6h
    _scheduler.add_job(
        _scrape_jobs,
        trigger=IntervalTrigger(hours=6),
        id='scrape_jobs',
        name='Scrape offres emploi IA',
        replace_existing=True,
    )

    # News toutes les 4h
    _scheduler.add_job(
        _scrape_news,
        trigger=IntervalTrigger(hours=4),
        id='scrape_news',
        name='Scrape actualités IA',
        replace_existing=True,
    )

    # Formations toutes les 12h
    _scheduler.add_job(
        _scrape_formations,
        trigger=IntervalTrigger(hours=12),
        id='scrape_formations',
        name='Scrape formations IA',
        replace_existing=True,
    )

    _scheduler.start()
    logger.info('[Scheduler] Background scheduler started — jobs: 6h, news: 4h, formations: 12h')


def _scrape_jobs():
    """Scrape les offres d'emploi depuis toutes les sources."""
    try:
        logger.info('[Scheduler] Lancement scrape_jobs...')
        call_command('scrape_jobs', '--source', 'all', '--limit', '20')
        logger.info('[Scheduler] scrape_jobs terminé.')
    except Exception as e:
        logger.error(f'[Scheduler] Erreur scrape_jobs: {e}')


def _scrape_news():
    """Scrape les actualités IA."""
    try:
        logger.info('[Scheduler] Lancement scrape_news...')
        call_command('scrape_news', '--limit', '30')
        logger.info('[Scheduler] scrape_news terminé.')
    except Exception as e:
        logger.error(f'[Scheduler] Erreur scrape_news: {e}')


def _scrape_formations():
    """Scrape les formations IA."""
    try:
        logger.info('[Scheduler] Lancement scrape_formations...')
        call_command('scrape_formations')
        logger.info('[Scheduler] scrape_formations terminé.')
    except Exception as e:
        logger.error(f'[Scheduler] Erreur scrape_formations: {e}')
