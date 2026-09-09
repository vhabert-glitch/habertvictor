"""
Surface d'outils de l'agent.

Un outil = une entrée dans READ_TOOLS / RADAR_TOOLS (schéma envoyé à Claude)
+ une fonction dans HANDLERS. Pour étendre l'agent (données Django, scrapers,
autre SaaS), il suffit d'ajouter une paire ici — la boucle ne change pas.

Aucun outil d'écriture n'existe ici, volontairement : l'agent lit Notion, il
n'y écrit jamais et n'y apparaît pas. Voir apps/agent/notion.py.
"""
import json

from . import documents, memoire, notion, radar

MEMOIRE_TOOLS = [
    {
        'name': 'memoire_rapports',
        'description': (
            "Liste tes propres rapports d'analyse précédents, du plus récent au plus "
            "ancien, avec leur date, leur mission et leur synthèse. "
            "À APPELER EN PREMIER, avant tout autre outil : c'est ce qui te dit ce que "
            "tu as déjà constaté et recommandé, et donc ce qui a bougé depuis. "
            "S'il n'y a aucun rapport antérieur, c'est ta première analyse."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'limit': {'type': 'integer',
                          'description': "Nombre de rapports, max 20, défaut 5."},
                'type': {'type': 'string', 'enum': ['fond', 'quotidien'],
                         'description': "Filtrer : 'fond' = analyses hebdomadaires, "
                                        "'quotidien' = points du matin. Vide = les deux."},
            },
            'required': [],
            'additionalProperties': False,
        },
    },
    {
        'name': 'memoire_lire',
        'description': (
            "Relit un rapport précédent en détail — entier, ou limité à une section "
            "(Synthèse, Analyse, Recommandations, Agenda, Angles morts). "
            "Utilise-le quand la synthèse ne suffit pas : pour retrouver ce que tu "
            "avais exactement recommandé sur un sujet, ou l'échéance que tu avais posée."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'rapport': {'type': 'string',
                            'description': "Identifiant vu dans memoire_rapports, "
                                           "ex: 2026-09-07-1024."},
                'section': {'type': 'string',
                            'description': "Section à extraire. Vide = rapport entier "
                                           "(volumineux, ~24 000 caractères)."},
            },
            'required': ['rapport'],
            'additionalProperties': False,
        },
    },
]

DOCUMENTS_TOOLS = [
    {
        'name': 'documents_lister',
        'description': (
            "Liste les synthèses et notes déposées par l'utilisateur (dossier "
            "Agent/Syntheses/), avec leur date de modification et un aperçu. On y trouve "
            "ce qui n'est ni dans Notion ni dans le radar : synthèses du projet "
            "tenues sur claude.ai, notes de stratégie, comptes rendus. "
            "À consulter tôt : ces documents portent souvent le raisonnement et les "
            "décisions que les bases Notion ne font qu'enregistrer."
        ),
        'input_schema': {'type': 'object', 'properties': {}, 'required': [],
                         'additionalProperties': False},
    },
    {
        'name': 'documents_lire',
        'description': (
            "Renvoie le texte intégral d'un document de contexte. Utilise-le quand "
            "l'aperçu ne suffit pas."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'document': {'type': 'string',
                             'description': "Nom vu dans documents_lister, "
                                            "ex: synthese-projet-claude.md."},
            },
            'required': ['document'],
            'additionalProperties': False,
        },
    },
]

RADAR_TOOLS = [
    {
        'name': 'radar_overview',
        'description': (
            "Inventaire des données scrapées par la plateforme : pour chaque jeu de "
            "données, le nombre de lignes, la période couverte, les champs sur lesquels "
            "on peut agréger et les métriques disponibles. "
            "À appeler AVANT tout autre outil radar — c'est ce qui te dit quels noms de "
            "champs sont valides. Aucun paramètre."
        ),
        'input_schema': {'type': 'object', 'properties': {}, 'required': [],
                         'additionalProperties': False},
    },
    {
        'name': 'radar_aggregate',
        'description': (
            "Compte les lignes d'un jeu de données par valeur d'un champ, trié par "
            "fréquence décroissante, avec la part en pourcentage. C'est l'outil "
            "principal : préfère-le toujours à la lecture de lignes une par une. "
            "Les champs de type liste (compétences, secteurs, hashtags) sont éclatés "
            "automatiquement — une ligne portant 3 compétences compte pour 3."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'dataset': {'type': 'string',
                            'description': "Nom du jeu, voir radar_overview."},
                'group_by': {'type': 'string',
                             'description': "Champ d'agrégation, voir 'grouper_par'."},
                'depuis_jours': {'type': 'integer',
                                 'description': "Ne garder que les N derniers jours."},
                'limit': {'type': 'integer', 'description': "Max 100, défaut 20."},
                'metric': {'type': 'string',
                           'description': "Métrique numérique à sommer/moyenner, "
                                          "voir 'metriques' dans radar_overview."},
            },
            'required': ['dataset', 'group_by'],
            'additionalProperties': False,
        },
    },
    {
        'name': 'radar_sample',
        'description': (
            "Renvoie quelques lignes réelles d'un jeu de données, pour illustrer ou "
            "vérifier ce qu'une agrégation suggère. Volontairement plafonné à 40 lignes : "
            "sert à étayer, pas à recompter."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'dataset': {'type': 'string'},
                'limit': {'type': 'integer', 'description': "Max 40, défaut 10."},
                'depuis_jours': {'type': 'integer'},
                'order_by': {'type': 'string',
                             'description': "Champ de tri, préfixé de '-' pour décroissant. "
                                            "Défaut : le plus récent."},
                'where': {
                    'type': 'object',
                    'description': "Filtres Django, ex: {\"sector\": \"sante\"} ou "
                                   "{\"title__icontains\": \"prompt\"}.",
                },
            },
            'required': ['dataset'],
            'additionalProperties': False,
        },
    },
    {
        'name': 'radar_search',
        'description': (
            "Cherche un terme dans les champs libres (titres, descriptions, résumés) "
            "d'un ou plusieurs jeux de données. Utile pour vérifier si un sujet vu "
            "dans Notion apparaît dans les données du marché — et à quelle fréquence."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'datasets': {
                    'type': 'array', 'items': {'type': 'string'},
                    'description': "Jeux à interroger. Vide = tous.",
                },
                'limit': {'type': 'integer', 'description': "Extraits par jeu, max 25, défaut 8."},
            },
            'required': ['query'],
            'additionalProperties': False,
        },
    },
]

READ_TOOLS = [
    {
        'name': 'notion_search',
        'description': (
            "Cherche les pages et bases de données Notion partagées avec l'intégration. "
            "À appeler en premier pour découvrir ce qui est accessible. "
            "Une requête vide renvoie tout ce qui est accessible."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': "Mots-clés. Vide = tout lister."},
                'object_type': {
                    'type': 'string', 'enum': ['page', 'database'],
                    'description': "Restreindre aux pages ou aux bases.",
                },
                'page_size': {'type': 'integer', 'description': "Max 100, défaut 25."},
            },
            'required': [],
            'additionalProperties': False,
        },
    },
    {
        'name': 'notion_get_database',
        'description': (
            "Renvoie le schéma d'une base : nom et type de chaque colonne, plus les "
            "options disponibles pour les colonnes select/multi_select/status. "
            "À appeler avant notion_query_database pour savoir sur quoi raisonner."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {'database_id': {'type': 'string'}},
            'required': ['database_id'],
            'additionalProperties': False,
        },
    },
    {
        'name': 'notion_query_database',
        'description': (
            "Liste les lignes d'une base Notion avec leurs propriétés aplaties. "
            "Pagine avec start_cursor tant que has_more vaut true. "
            "Filtres et tris suivent la syntaxe de l'API Notion."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'database_id': {'type': 'string'},
                'page_size': {'type': 'integer', 'description': "Max 100, défaut 50."},
                'start_cursor': {'type': 'string', 'description': "Curseur de pagination."},
                'sorts': {
                    'type': 'array',
                    'description': "Ex: [{\"property\": \"Date\", \"direction\": \"descending\"}]",
                    'items': {'type': 'object'},
                },
                'filter': {
                    'type': 'object',
                    'description': "Filtre Notion, ex: {\"property\": \"Statut\", \"status\": {\"equals\": \"En cours\"}}",
                },
            },
            'required': ['database_id'],
            'additionalProperties': False,
        },
    },
    {
        'name': 'notion_get_page_content',
        'description': (
            "Renvoie le contenu textuel d'une page Notion (titres, paragraphes, listes, "
            "cases à cocher). Utile quand les propriétés d'une ligne ne suffisent pas "
            "et qu'il faut lire le corps de la page."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'page_id': {'type': 'string'},
                'max_blocks': {'type': 'integer', 'description': "Défaut 100."},
            },
            'required': ['page_id'],
            'additionalProperties': False,
        },
    },
]


def web_tool(max_uses):
    """Recherche web exécutée côté Anthropic — rien à héberger chez nous.

    Plafonnée en nombre de recherches : sans plafond, le modèle a tendance à
    aller chercher sur le web ce qu'il pourrait compter dans le radar, ce qui
    coûte plus cher pour un résultat moins fiable.
    """
    return {
        'type': 'web_search_20260209',
        'name': 'web_search',
        'max_uses': max_uses,
    }


def build_toolset(with_notion=True, with_radar=True, web_max_uses=0,
                  with_memoire=True, with_documents=True):
    """Renvoie la liste d'outils exposée à Claude pour cette exécution."""
    toolset = []
    if with_memoire:
        toolset += MEMOIRE_TOOLS
    if with_documents:
        toolset += DOCUMENTS_TOOLS
    if with_notion:
        toolset += READ_TOOLS
    if with_radar:
        toolset += RADAR_TOOLS
    if web_max_uses:
        toolset.append(web_tool(web_max_uses))
    return toolset


def dispatch(name, payload):
    """Exécute un outil et renvoie une chaîne prête à repartir vers Claude."""
    if name == 'memoire_rapports':
        result = memoire.rapports(limit=payload.get('limit') or 5,
                                  type=payload.get('type'))
    elif name == 'memoire_lire':
        result = memoire.lire(payload['rapport'], section=payload.get('section') or None)
    elif name == 'documents_lister':
        result = documents.lister()
    elif name == 'documents_lire':
        return documents.lire(payload['document'])['contenu']
    elif name == 'radar_overview':
        result = radar.overview()
    elif name == 'radar_aggregate':
        result = radar.aggregate(
            payload['dataset'], payload['group_by'],
            depuis_jours=payload.get('depuis_jours'),
            limit=payload.get('limit') or 20,
            metric=payload.get('metric'),
        )
    elif name == 'radar_sample':
        result = radar.sample(
            payload['dataset'],
            limit=payload.get('limit') or 10,
            depuis_jours=payload.get('depuis_jours'),
            order_by=payload.get('order_by'),
            where=payload.get('where'),
        )
    elif name == 'radar_search':
        result = radar.search(
            payload['query'],
            datasets=payload.get('datasets') or None,
            limit=payload.get('limit') or 8,
        )
    elif name == 'notion_search':
        result = notion.search(
            query=payload.get('query', ''),
            object_type=payload.get('object_type'),
            page_size=payload.get('page_size') or 25,
        )
    elif name == 'notion_get_database':
        result = notion.get_database(payload['database_id'])
    elif name == 'notion_query_database':
        result = notion.query_database(
            payload['database_id'],
            page_size=payload.get('page_size') or 50,
            start_cursor=payload.get('start_cursor'),
            sorts=payload.get('sorts'),
            filter_=payload.get('filter'),
        )
    elif name == 'notion_get_page_content':
        return notion.get_page_content(
            payload['page_id'], max_blocks=payload.get('max_blocks') or 100,
        ) or '(page vide)'
    else:
        raise ValueError(f"Outil inconnu : {name}")

    return json.dumps(result, ensure_ascii=False, indent=None)
