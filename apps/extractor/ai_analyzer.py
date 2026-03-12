"""
Module d'analyse IA : utilise l'API Claude pour résumer et analyser
les données extraites, détecter des tendances et générer des rapports.
"""
import json
import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)


def get_client():
    """Retourne un client Anthropic configuré."""
    api_key = settings.ANTHROPIC_API_KEY or os.getenv('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.error("Le package 'anthropic' n'est pas installé.")
        return None


def summarize_article(title, content, max_tokens=300):
    """Résume un article d'actualité et extrait les infos clés."""
    client = get_client()
    if not client:
        return None

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": (
                    f"Résume cet article en 2-3 phrases en français. "
                    f"Identifie aussi : les secteurs concernés, les compétences IA mentionnées, "
                    f"et le niveau d'urgence perçu.\n\n"
                    f"Titre : {title}\n"
                    f"Contenu : {content[:3000]}\n\n"
                    f"Réponds en JSON :\n"
                    f'{{"resume": "...", "secteurs": [...], "competences": [...], "urgence": "faible|moyenne|forte"}}'
                )
            }]
        )
        text = response.content[0].text.strip()
        # Extraire le JSON de la réponse
        if '{' in text:
            json_str = text[text.index('{'):text.rindex('}') + 1]
            return json.loads(json_str)
    except Exception as e:
        logger.error(f"Erreur résumé article: {e}")
    return None


def analyze_trends(data_summary, max_tokens=800):
    """Analyse les tendances à partir des données agrégées."""
    client = get_client()
    if not client:
        return None

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": (
                    f"Tu es un analyste spécialisé dans les besoins en formation IA en France.\n"
                    f"Voici un résumé des données collectées cette semaine :\n\n"
                    f"{data_summary}\n\n"
                    f"Analyse ces données et produis :\n"
                    f"1. Les 3 tendances principales détectées\n"
                    f"2. Les 5 compétences IA les plus demandées\n"
                    f"3. Les secteurs avec les besoins les plus urgents\n"
                    f"4. Recommandations pour l'offre de formation\n\n"
                    f"Réponds en JSON :\n"
                    f'{{"tendances": ["..."], "competences_top": ["..."], '
                    f'"secteurs_urgents": ["..."], "recommandations": ["..."]}}'
                )
            }]
        )
        text = response.content[0].text.strip()
        if '{' in text:
            json_str = text[text.index('{'):text.rindex('}') + 1]
            return json.loads(json_str)
    except Exception as e:
        logger.error(f"Erreur analyse tendances: {e}")
    return None


def generate_weekly_report(stats):
    """Génère un rapport hebdomadaire en texte structuré."""
    client = get_client()
    if not client:
        return None

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": (
                    f"Tu es un analyste expert en formation IA en France.\n"
                    f"Génère un rapport hebdomadaire concis basé sur ces statistiques :\n\n"
                    f"{json.dumps(stats, ensure_ascii=False, indent=2)}\n\n"
                    f"Le rapport doit inclure :\n"
                    f"- Résumé exécutif (3 lignes)\n"
                    f"- Faits marquants de la semaine\n"
                    f"- Évolution des besoins par secteur\n"
                    f"- Signaux faibles détectés\n"
                    f"- Actions recommandées\n\n"
                    f"Format : Markdown structuré en français."
                )
            }]
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Erreur génération rapport: {e}")
    return None
