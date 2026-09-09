"""
Mémoire de l'agent : ses propres rapports passés.

L'agent repartait de zéro à chaque exécution. Il resignalait les mêmes points
sans savoir s'ils avaient déjà été soulevés, et surtout sans pouvoir dire si
une recommandation avait été suivie. Or c'est là qu'est la valeur d'un suivi
hebdomadaire : « je te l'avais dit le 7/09, trois semaines après rien n'a bougé »
vaut bien plus que de reformuler le même constat chaque lundi.

Les rapports sont les fichiers markdown écrits par la commande `agent_run`
dans Agent/Technique/memoire/. Aucune base de données, aucun format nouveau : la mémoire,
ce sont les livrables eux-mêmes.

Économie de contexte : lister les rapports ne renvoie que leur *synthèse*
(quelques centaines de mots), pas leur texte intégral (~24 000 caractères).
L'agent ne lit un rapport en entier que s'il a besoin du détail.
"""
import datetime as dt
import re
from pathlib import Path

from django.conf import settings

# Les .md vivent à l'écart : l'utilisateur ne doit voir que les .docx dans
# Rapports/ et Points du jour/. Deux fichiers par rapport dans le même dossier,
# c'était illisible.
DOSSIERS = [Path(settings.BASE_DIR) / 'Agent' / 'Technique' / 'memoire']

# nom écrit par agent_run, pensé pour être lisible dans le Finder :
#   « 2026-09-07 - Analyse de fond (10h24) »
#   « 2026-09-08 - Point du jour (07h30) »
NOM_RAPPORT = re.compile(
    r'^(\d{4})-(\d{2})-(\d{2}) - (Analyse de fond|Point du jour) \((\d{2})h(\d{2})\)$'
)


class MemoireError(ValueError):
    """Rapport introuvable — le message repart à l'agent."""


def _horodatage(stem):
    m = NOM_RAPPORT.match(stem)
    if not m:
        return None
    an, mois, jour = (int(x) for x in m.group(1, 2, 3))
    h, mn = int(m.group(5)), int(m.group(6))
    try:
        return dt.datetime(an, mois, jour, h, mn)
    except ValueError:
        return None


def _type(stem):
    m = NOM_RAPPORT.match(stem)
    return m.group(4) if m else 'inconnu'


def _section(texte, titre):
    """Extrait une section « ## Titre » jusqu'au prochain titre de même niveau."""
    debut = re.search(rf'^##\s+{re.escape(titre)}\s*$', texte, re.M | re.I)
    if not debut:
        return ''
    reste = texte[debut.end():]
    suite = re.search(r'^##\s+', reste, re.M)
    return (reste[:suite.start()] if suite else reste).strip()


def _fichiers():
    dates = []
    for dossier in DOSSIERS:
        if not dossier.exists():
            continue
        for chemin in dossier.glob('*.md'):
            quand = _horodatage(chemin.stem)
            if quand:
                dates.append((quand, chemin))
    return sorted(dates, key=lambda x: x[0], reverse=True)


def rapports(limit=5, avec_syntheses=True, type=None):
    """Liste les rapports passés, du plus récent au plus ancien.

    `type` filtre sur 'quotidien' ou 'fond'. Utile parce qu'un point du matin
    quotidien produirait sinon sept rapports par semaine, qui masqueraient
    l'analyse de fond hebdomadaire dans une liste courte.
    """
    limit = max(1, min(int(limit or 5), 20))
    fichiers = _fichiers()
    if type == 'quotidien':
        fichiers = [f for f in fichiers if _type(f[1].stem) == 'Point du jour']
    elif type == 'fond':
        fichiers = [f for f in fichiers if _type(f[1].stem) == 'Analyse de fond']

    sortie = []
    for quand, chemin in fichiers[:limit]:
        texte = chemin.read_text(encoding='utf-8', errors='replace')
        mission = re.search(r'^\*\*Mission :\*\*\s*(.+)$', texte, re.M)
        entree = {
            'rapport': chemin.stem,
            'type': _type(chemin.stem),
            'date': quand.strftime('%Y-%m-%d %H:%M'),
            'il_y_a_jours': (dt.datetime.now() - quand).days,
            'mission': mission.group(1).strip() if mission else '',
            'taille': len(texte),
        }
        if avec_syntheses:
            # un point quotidien n'a pas de « Synthèse » : on prend ses deux
            # sections utiles à la place
            extrait = _section(texte, 'Synthèse')
            if not extrait:
                extrait = '\n'.join(filter(None, [
                    _section(texte, 'À faire aujourd\'hui'),
                    _section(texte, 'Ce qui mérite ton attention'),
                ]))
            entree['synthese'] = extrait or '(pas de résumé extractible)'
        sortie.append(entree)

    if not sortie:
        return {'rapports': [],
                'note': "Aucun rapport antérieur : c'est la première analyse. "
                        "Ne fais pas de comparaison avec le passé."}
    return {'rapports': sortie, 'total_en_archive': len(_fichiers())}


def lire(rapport, section=None):
    """Renvoie un rapport passé, entier ou limité à une section."""
    chemins = {c.stem: c for _, c in _fichiers()}
    if rapport not in chemins:
        raise MemoireError(
            f"Rapport '{rapport}' introuvable. Disponibles : "
            f"{', '.join(sorted(chemins, reverse=True)[:10]) or 'aucun'}."
        )
    texte = chemins[rapport].read_text(encoding='utf-8', errors='replace')

    if section:
        extrait = _section(texte, section)
        if not extrait:
            raise MemoireError(
                f"Section '{section}' absente de {rapport}. Sections : "
                "Plan, Synthèse, Analyse, Recommandations, Agenda, Angles morts."
            )
        return {'rapport': rapport, 'section': section, 'contenu': extrait}

    return {'rapport': rapport, 'contenu': texte}
