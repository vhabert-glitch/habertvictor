"""
Client Notion minimal (REST v1) pour l'agent.

Deux principes :
  - lecture seule, sans exception : ce module ne contient aucune fonction
    d'écriture. L'agent ne crée rien dans Notion et n'y apparaît pas ;
  - les réponses Notion sont *aplaties* avant d'être renvoyées à Claude.
    Le JSON brut de Notion est très verbeux (une propriété "title" fait
    ~15 lignes) : l'aplatir divise la consommation de tokens par 10 environ.
"""
import logging
import os

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_ROOT = 'https://api.notion.com/v1'
DEFAULT_TIMEOUT = 30


class NotionError(RuntimeError):
    """Erreur renvoyée par l'API Notion (remontée telle quelle à l'agent)."""


def _token():
    return getattr(settings, 'NOTION_API_KEY', '') or os.getenv('NOTION_API_KEY', '')


def _version():
    return getattr(settings, 'NOTION_VERSION', '') or os.getenv('NOTION_VERSION', '2022-06-28')


def is_configured():
    return bool(_token())


def _request(method, path, payload=None, params=None):
    token = _token()
    if not token:
        raise NotionError(
            "NOTION_API_KEY absent. Crée une intégration sur "
            "https://www.notion.so/my-integrations, puis renseigne la clé dans .env"
        )

    headers = {
        'Authorization': f'Bearer {token}',
        'Notion-Version': _version(),
        'Content-Type': 'application/json',
    }
    url = f'{API_ROOT}{path}'

    try:
        response = requests.request(
            method, url, headers=headers, json=payload, params=params,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise NotionError(f"Appel Notion impossible ({url}) : {exc}") from exc

    if response.status_code == 401:
        raise NotionError("Notion refuse la clé (401). Vérifie NOTION_API_KEY.")
    if response.status_code == 404:
        raise NotionError(
            "Objet introuvable (404). Le plus souvent l'intégration n'a pas été "
            "partagée avec cette page/base : dans Notion, ouvre la page → "
            "menu ••• → Connexions → ajoute ton intégration."
        )
    if response.status_code >= 400:
        raise NotionError(f"Erreur Notion {response.status_code} : {response.text[:400]}")

    return response.json()


# ─────────────────────────────────────────────────────────────
#  Aplatissement des structures Notion
# ─────────────────────────────────────────────────────────────

def _plain_text(rich_text):
    return ''.join(part.get('plain_text', '') for part in rich_text or []).strip()


def flatten_property(prop):
    """Réduit une propriété Notion à une valeur Python simple."""
    if not isinstance(prop, dict):
        return None
    kind = prop.get('type')

    if kind in ('title', 'rich_text'):
        return _plain_text(prop.get(kind))
    if kind in ('number', 'checkbox', 'url', 'email', 'phone_number'):
        return prop.get(kind)
    if kind == 'select':
        return (prop.get('select') or {}).get('name')
    if kind == 'status':
        return (prop.get('status') or {}).get('name')
    if kind == 'multi_select':
        return [opt.get('name') for opt in prop.get('multi_select') or []]
    if kind == 'date':
        date = prop.get('date') or {}
        start, end = date.get('start'), date.get('end')
        return f'{start} → {end}' if end else start
    if kind == 'people':
        return [p.get('name') or p.get('id') for p in prop.get('people') or []]
    if kind == 'files':
        return [f.get('name') for f in prop.get('files') or []]
    if kind == 'relation':
        return [r.get('id') for r in prop.get('relation') or []]
    if kind in ('created_time', 'last_edited_time'):
        return prop.get(kind)
    if kind in ('created_by', 'last_edited_by'):
        return (prop.get(kind) or {}).get('name')
    if kind == 'unique_id':
        uid = prop.get('unique_id') or {}
        prefix = uid.get('prefix') or ''
        return f"{prefix}{uid.get('number')}"
    if kind == 'formula':
        formula = prop.get('formula') or {}
        return formula.get(formula.get('type'))
    if kind == 'rollup':
        rollup = prop.get('rollup') or {}
        if rollup.get('type') == 'array':
            return [flatten_property(item) for item in rollup.get('array') or []]
        return rollup.get(rollup.get('type'))
    return None


def flatten_page(page):
    """Transforme une page Notion en dict plat {titre, url, propriétés}."""
    props = page.get('properties') or {}
    flat, title = {}, None
    for name, prop in props.items():
        value = flatten_property(prop)
        if prop.get('type') == 'title':
            title = value
        if value not in (None, '', [], {}):
            flat[name] = value
    return {
        'id': page.get('id'),
        'titre': title,
        'url': page.get('url'),
        'derniere_modif': page.get('last_edited_time'),
        'proprietes': flat,
    }


BLOCK_PREFIXES = {
    'heading_1': '# ',
    'heading_2': '## ',
    'heading_3': '### ',
    'bulleted_list_item': '- ',
    'numbered_list_item': '- ',
    'quote': '> ',
    'to_do': '- [ ] ',
    'toggle': '',
    'paragraph': '',
    'callout': '',
}


def flatten_block(block):
    """Rend un bloc Notion sous forme d'une ligne de texte (ou None)."""
    kind = block.get('type')
    body = block.get(kind) or {}

    if kind == 'code':
        code = _plain_text(body.get('rich_text'))
        return f"```{body.get('language', '')}\n{code}\n```" if code else None
    if kind == 'child_page':
        return f"[sous-page] {body.get('title', '')}"
    if kind == 'child_database':
        return f"[base liée] {body.get('title', '')}"
    if kind in BLOCK_PREFIXES:
        text = _plain_text(body.get('rich_text'))
        if not text:
            return None
        prefix = BLOCK_PREFIXES[kind]
        if kind == 'to_do':
            prefix = '- [x] ' if body.get('checked') else '- [ ] '
        return f'{prefix}{text}'
    return None


# ─────────────────────────────────────────────────────────────
#  Lecture
# ─────────────────────────────────────────────────────────────

def search(query='', object_type=None, page_size=25):
    """Cherche pages et bases partagées avec l'intégration."""
    payload = {'page_size': min(page_size, 100)}
    if query:
        payload['query'] = query
    if object_type in ('page', 'database'):
        payload['filter'] = {'property': 'object', 'value': object_type}

    data = _request('POST', '/search', payload)
    results = []
    for item in data.get('results', []):
        if item.get('object') == 'database':
            results.append({
                'type': 'database',
                'id': item.get('id'),
                'titre': _plain_text(item.get('title')),
                'url': item.get('url'),
            })
        else:
            flat = flatten_page(item)
            results.append({
                'type': 'page',
                'id': flat['id'],
                'titre': flat['titre'],
                'url': flat['url'],
            })
    return results


def get_database(database_id):
    """Renvoie le schéma d'une base : nom + type de chaque colonne."""
    data = _request('GET', f'/databases/{database_id}')
    schema = {}
    for name, prop in (data.get('properties') or {}).items():
        kind = prop.get('type')
        entry = {'type': kind}
        if kind in ('select', 'multi_select', 'status'):
            options = (prop.get(kind) or {}).get('options') or []
            entry['options'] = [opt.get('name') for opt in options]
        schema[name] = entry
    return {
        'id': data.get('id'),
        'titre': _plain_text(data.get('title')),
        'url': data.get('url'),
        'colonnes': schema,
    }


def query_database(database_id, page_size=50, start_cursor=None, sorts=None, filter_=None):
    """Liste les lignes d'une base, aplaties."""
    payload = {'page_size': min(page_size, 100)}
    if start_cursor:
        payload['start_cursor'] = start_cursor
    if sorts:
        payload['sorts'] = sorts
    if filter_:
        payload['filter'] = filter_

    data = _request('POST', f'/databases/{database_id}/query', payload)
    return {
        'lignes': [flatten_page(page) for page in data.get('results', [])],
        'has_more': data.get('has_more', False),
        'next_cursor': data.get('next_cursor'),
    }


def get_page_content(page_id, max_blocks=100):
    """Renvoie le contenu textuel d'une page (blocs de premier niveau)."""
    lines, cursor, fetched = [], None, 0
    while fetched < max_blocks:
        params = {'page_size': min(100, max_blocks - fetched)}
        if cursor:
            params['start_cursor'] = cursor
        data = _request('GET', f'/blocks/{page_id}/children', params=params)
        blocks = data.get('results', [])
        fetched += len(blocks)
        for block in blocks:
            line = flatten_block(block)
            if line:
                lines.append(line)
        if not data.get('has_more'):
            break
        cursor = data.get('next_cursor')
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────
#  Écriture : volontairement absente
#
#  L'espace Notion est partagé avec l'équipe et son propriétaire ne veut pas
#  que l'agent y soit visible ni qu'il y crée quoi que ce soit. Il n'existe
#  donc aucune fonction d'écriture dans ce module — pas de garde à contourner,
#  pas d'option à oublier : la capacité n'existe pas.
#
#  Le jeton Notion devrait par ailleurs être créé en lecture seule
#  (capability « Read content » uniquement) pour que Notion l'interdise aussi
#  de son côté.
# ─────────────────────────────────────────────────────────────
