"""
Accès aux données scrapées du radar (modèles Django) pour l'agent.

Règle de conception : l'agent ne lit jamais 665 offres d'emploi ligne par ligne.
Il agrège (`aggregate`), puis échantillonne (`sample`) une poignée de lignes pour
étayer ce qu'il avance. C'est ce qui fait tenir une analyse sur l'ensemble du
corpus dans un contexte raisonnable.

Ajouter une source de données = ajouter une entrée dans DATASETS.
"""
import datetime as dt
import json
from collections import Counter, defaultdict

from django.apps import apps
from django.db.models import Avg, Count, Q, Sum

TEXT_LIMIT = 280  # troncature des champs libres dans les échantillons


def _model(label):
    app_label, model_name = label.split('.')
    return apps.get_model(app_label, model_name)


# ─────────────────────────────────────────────────────────────
#  Registre des jeux de données
#
#  date      : champ de datation utilisé par le filtre `depuis_jours`
#  groupes   : champs scalaires agrégeables (relations `__` autorisées)
#  listes    : champs JSON contenant une liste, éclatés à l'agrégation
#  metriques : champs numériques agrégeables → 'somme' ou 'moyenne'
#  texte     : champs balayés par la recherche plein texte
#  colonnes  : champs renvoyés par les échantillons
# ─────────────────────────────────────────────────────────────

DATASETS = {
    'offres': {
        'modele': 'extractor.JobPosting',
        'description': "Offres d'emploi mentionnant des compétences IA",
        'date': 'extracted_at',
        'groupes': ['sector', 'company', 'source', 'training_type_match', 'location'],
        'listes': ['skills'],
        'metriques': {'relevance_score': 'moyenne'},
        'texte': ['title', 'company', 'raw_description', 'location'],
        'colonnes': ['title', 'company', 'source', 'sector', 'skills', 'location',
                     'training_type_match', 'relevance_score', 'url', 'extracted_at'],
    },
    'actus': {
        'modele': 'extractor.NewsArticle',
        'description': "Articles de presse et de veille",
        'date': 'published_at',
        'groupes': ['source'],
        'listes': ['sectors', 'issues'],
        'metriques': {'relevance_score': 'moyenne'},
        'texte': ['title', 'summary'],
        'colonnes': ['title', 'source', 'summary', 'sectors', 'issues',
                     'relevance_score', 'url', 'published_at'],
    },
    'communaute': {
        'modele': 'extractor.CommunityPost',
        'description': "Posts Reddit / forums / communautés professionnelles",
        'date': 'published_at',
        'groupes': ['platform', 'subreddit', 'sector', 'training_type_match'],
        'listes': ['skills_mentioned'],
        'metriques': {'score': 'moyenne', 'comments_count': 'moyenne',
                      'relevance_score': 'moyenne'},
        'texte': ['title', 'content_summary'],
        'colonnes': ['title', 'platform', 'subreddit', 'sector', 'skills_mentioned',
                     'score', 'comments_count', 'url', 'published_at'],
    },
    'tendances': {
        'modele': 'extractor.TrendData',
        'description': "Mesures de tendance (volumes de recherche, mentions) par mot-clé",
        'date': 'measured_at',
        'groupes': ['source', 'keyword', 'category', 'region'],
        'listes': [],
        'metriques': {'value': 'moyenne'},
        'texte': ['keyword', 'category'],
        'colonnes': ['keyword', 'source', 'value', 'category', 'region', 'measured_at'],
    },
    'social': {
        'modele': 'extractor.SocialSignal',
        'description': "Signaux réseaux sociaux avec sentiment",
        'date': 'detected_at',
        'groupes': ['platform', 'sector', 'sentiment'],
        'listes': ['hashtags'],
        'metriques': {'relevance_score': 'moyenne'},
        'texte': ['content_summary'],
        'colonnes': ['content_summary', 'platform', 'sector', 'sentiment',
                     'hashtags', 'url', 'detected_at'],
    },
    'marches': {
        'modele': 'extractor.PublicTender',
        'description': "Appels d'offres publics IA, issus de l'API open data BOAMP "
                       "(DILA). Chaque avis a une URL vérifiable et une date limite "
                       "de réponse réelle — c'est la meilleure source d'échéances "
                       "datées pour construire un agenda.",
        'date': 'extracted_at',
        'groupes': ['sector', 'org', 'source'],
        'listes': [],
        'metriques': {},
        'texte': ['title', 'description', 'org', 'budget'],
        'colonnes': ['title', 'org', 'budget', 'deadline', 'sector', 'url', 'extracted_at'],
    },
    'formations': {
        'modele': 'extractor.FormationCatalog',
        'description': "Catalogue des formations IA existantes sur le marché — "
                       "la référence pour repérer ce que l'offre ne couvre pas",
        'fiabilite': "TABLE VIDE — la source n'est pas branchée (l'API visée par le "
                     "scraper n'existe pas ; les lignes fictives qui la remplissaient "
                     "ont été supprimées). Tu n'as donc AUCUNE vision de l'offre de "
                     "formation du marché. Si on te demande ce qui « n'est couvert par "
                     "aucune formation », réponds que tu ne peux pas le déterminer et "
                     "explique pourquoi, au lieu de conclure sur une table vide.",
        'date': 'extracted_at',
        'groupes': ['sector', 'training_type', 'provider', 'format'],
        'listes': ['skills_covered'],
        'metriques': {},
        'texte': ['name', 'description', 'provider'],
        'colonnes': ['name', 'provider', 'sector', 'training_type', 'format',
                     'price', 'duration', 'skills_covered', 'url'],
    },
    'enquetes': {
        'modele': 'survey.SurveyResponse',
        'description': "Réponses des entreprises au questionnaire besoins IA "
                       "(déclaratif, contrairement aux données scrapées)",
        'date': 'submitted_at',
        'groupes': ['ai_maturity', 'budget', 'preferred_format',
                    'company__sector', 'company__size', 'is_complete'],
        'listes': ['priority_skills'],
        'metriques': {'trained_employees': 'somme'},
        'texte': ['ai_tools', 'free_text', 'company__name'],
        'colonnes': ['company__name', 'company__sector', 'company__size', 'ai_maturity',
                     'budget', 'preferred_format', 'priority_skills', 'trained_employees',
                     'free_text', 'submitted_at'],
    },
    'besoins': {
        'modele': 'survey.TrainingNeed',
        'description': "Besoins de formation déclarés, avec volumétrie de personnes à former",
        'date': 'response__submitted_at',
        'groupes': ['training_type', 'need_level', 'urgency',
                    'response__company__sector', 'response__company__size'],
        'listes': [],
        'metriques': {'people_count': 'somme'},
        'texte': ['response__company__name'],
        'colonnes': ['response__company__name', 'response__company__sector',
                     'training_type', 'need_level', 'urgency', 'people_count'],
    },
    'enjeux': {
        'modele': 'survey.CriticalIssueRanking',
        'description': "Classement des enjeux critiques par les entreprises (rang 1 = prioritaire)",
        'date': 'response__submitted_at',
        'groupes': ['issue_type', 'rank', 'response__company__sector'],
        'listes': [],
        'metriques': {'rank': 'moyenne'},
        'texte': ['response__company__name'],
        'colonnes': ['response__company__name', 'response__company__sector',
                     'issue_type', 'rank'],
    },
}


class RadarError(ValueError):
    """Paramètre invalide — le message repart à l'agent pour qu'il se corrige."""


def _spec(dataset):
    if dataset not in DATASETS:
        raise RadarError(
            f"Jeu de données inconnu : '{dataset}'. "
            f"Disponibles : {', '.join(sorted(DATASETS))}."
        )
    return DATASETS[dataset]


def _labels(model, field_path):
    """Table code → libellé pour les champs à choix (secteurs, tailles...)."""
    try:
        field = model._meta.get_field(field_path.split('__')[-1])
    except Exception:
        return {}
    return dict(field.choices or {})


def _queryset(dataset, depuis_jours=None):
    spec = _spec(dataset)
    model = _model(spec['modele'])
    qs = model.objects.all()
    if depuis_jours:
        from django.utils import timezone
        seuil = timezone.now() - dt.timedelta(days=int(depuis_jours))
        qs = qs.filter(**{f"{spec['date']}__gte": seuil})
    return qs, spec, model


def _shorten(value):
    if isinstance(value, str) and len(value) > TEXT_LIMIT:
        return value[:TEXT_LIMIT] + '…'
    if isinstance(value, dt.datetime):
        return value.isoformat(timespec='minutes')
    if isinstance(value, dt.date):  # DateField : pas de timespec sur un date
        return value.isoformat()
    return value


# ─────────────────────────────────────────────────────────────
#  Outils
# ─────────────────────────────────────────────────────────────

def overview():
    """Inventaire de tout ce que l'agent peut interroger. À appeler en premier."""
    from django.db.models import Max, Min

    out = {}
    for name, spec in DATASETS.items():
        model = _model(spec['modele'])
        total = model.objects.count()
        entry = {
            'description': spec['description'],
            'lignes': total,
            'grouper_par': spec['groupes'] + spec['listes'],
            'champs_listes': spec['listes'],
            'metriques': spec['metriques'],
            'champ_date': spec['date'],
        }
        if spec.get('fiabilite'):
            entry['⚠ fiabilite'] = spec['fiabilite']
        if total:
            bornes = model.objects.aggregate(
                debut=Min(spec['date']), fin=Max(spec['date']))
            entry['periode'] = {
                'debut': _shorten(bornes['debut']),
                'fin': _shorten(bornes['fin']),
            }
        out[name] = entry
    return out


def aggregate(dataset, group_by, depuis_jours=None, limit=20, metric=None):
    """Compte (et optionnellement somme/moyenne) les lignes par valeur de `group_by`."""
    qs, spec, model = _queryset(dataset, depuis_jours)
    champs = spec['groupes'] + spec['listes']
    if group_by not in champs:
        raise RadarError(
            f"'{group_by}' n'est pas agrégeable sur '{dataset}'. "
            f"Champs possibles : {', '.join(champs)}."
        )
    if metric and metric not in spec['metriques']:
        raise RadarError(
            f"Métrique '{metric}' indisponible sur '{dataset}'. "
            f"Métriques : {', '.join(spec['metriques']) or 'aucune'}."
        )

    limit = max(1, min(int(limit or 20), 100))
    total = qs.count()
    libelles = _labels(model, group_by)

    # Champ JSON contenant une liste : on éclate côté Python
    if group_by in spec['listes']:
        compteur = Counter()
        cumul = defaultdict(float)
        for valeurs, mesure in qs.values_list(group_by, metric or 'id'):
            if isinstance(valeurs, str):
                try:
                    valeurs = json.loads(valeurs)
                except ValueError:
                    valeurs = [valeurs]
            for item in valeurs or []:
                cle = str(item).strip()
                if not cle:
                    continue
                compteur[cle] += 1
                if metric and mesure is not None:
                    cumul[cle] += float(mesure)
        lignes = []
        for cle, n in compteur.most_common(limit):
            ligne = {'valeur': cle, 'n': n, 'part': round(100 * n / total, 1) if total else 0}
            if metric:
                brut = cumul[cle]
                ligne[metric] = round(brut if spec['metriques'][metric] == 'somme'
                                      else brut / n, 2)
            lignes.append(ligne)
    else:
        annotations = {'n': Count('id')}
        if metric:
            fonction = Sum if spec['metriques'][metric] == 'somme' else Avg
            annotations[metric] = fonction(metric)
        rows = qs.values(group_by).annotate(**annotations).order_by('-n')[:limit]
        lignes = []
        for row in rows:
            brut = row[group_by]
            cle = libelles.get(brut, brut)
            n = row['n']
            ligne = {
                'valeur': str(cle) if cle not in (None, '') else '(non renseigné)',
                'n': n,
                'part': round(100 * n / total, 1) if total else 0,
            }
            if metric and row.get(metric) is not None:
                ligne[metric] = round(float(row[metric]), 2)
            lignes.append(ligne)

    resultat = {
        'jeu': dataset,
        'groupe_par': group_by,
        'lignes_couvertes': total,
        'periode': f'{depuis_jours} derniers jours' if depuis_jours else 'tout l\'historique',
        'resultats': lignes,
    }
    if spec.get('fiabilite'):
        resultat['⚠ fiabilite'] = spec['fiabilite']
    return resultat


def sample(dataset, limit=10, depuis_jours=None, order_by=None, where=None):
    """Renvoie quelques lignes réelles, pour étayer une analyse par des exemples."""
    qs, spec, model = _queryset(dataset, depuis_jours)
    limit = max(1, min(int(limit or 10), 40))

    if where:
        if not isinstance(where, dict):
            raise RadarError("`where` doit être un objet {champ: valeur}.")
        autorises = set(spec['groupes'] + spec['listes'] + spec['texte'])
        filtres = {}
        for cle, valeur in where.items():
            champ = cle.split('__')[0] if '__' in cle else cle
            base = cle.replace('__icontains', '').replace('__gte', '').replace('__lte', '')
            if base not in autorises and champ not in autorises:
                raise RadarError(
                    f"Filtre '{cle}' non autorisé sur '{dataset}'. "
                    f"Champs filtrables : {', '.join(sorted(autorises))}."
                )
            filtres[cle] = valeur
        try:
            qs = qs.filter(**filtres)
        except Exception as exc:
            raise RadarError(f"Filtre invalide : {exc}")

    tri = order_by or f"-{spec['date']}"
    champ_tri = tri.lstrip('-')
    if champ_tri not in spec['colonnes'] + [spec['date']] + list(spec['metriques']):
        raise RadarError(f"Tri sur '{champ_tri}' non autorisé pour '{dataset}'.")

    total = qs.count()
    rows = qs.values(*spec['colonnes']).order_by(tri)[:limit]

    libelles = {c: _labels(model, c) for c in spec['colonnes']}
    lignes = []
    for row in rows:
        lignes.append({
            c: _shorten(libelles[c].get(v, v)) if libelles[c] else _shorten(v)
            for c, v in row.items()
        })
    return {'jeu': dataset, 'lignes_correspondantes': total,
            'affichees': len(lignes), 'echantillon': lignes}


def search(query, datasets=None, limit=8):
    """Recherche plein texte dans les champs libres d'un ou plusieurs jeux."""
    if not query or not query.strip():
        raise RadarError("`query` est vide.")
    cibles = datasets or list(DATASETS)
    inconnus = [d for d in cibles if d not in DATASETS]
    if inconnus:
        raise RadarError(f"Jeux inconnus : {', '.join(inconnus)}.")

    limit = max(1, min(int(limit or 8), 25))
    resultats = {}
    for nom in cibles:
        spec = DATASETS[nom]
        model = _model(spec['modele'])
        condition = Q()
        for champ in spec['texte']:
            condition |= Q(**{f'{champ}__icontains': query})
        qs = model.objects.filter(condition)
        total = qs.count()
        if not total:
            continue
        rows = qs.values(*spec['colonnes']).order_by(f"-{spec['date']}")[:limit]
        resultats[nom] = {
            'total': total,
            'extraits': [{c: _shorten(v) for c, v in row.items()} for row in rows],
        }
    return {'requete': query, 'resultats': resultats} if resultats else {
        'requete': query, 'resultats': {}, 'note': "Aucune correspondance."}
