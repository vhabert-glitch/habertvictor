"""
Documents de contexte : la matière qui n'est ni dans Notion ni dans le radar.

Typiquement la synthèse du Projet NEXUS sur claude.ai. Les Projets claude.ai
n'ont aucune API — rien ne peut aller les lire automatiquement. Le pont est
donc manuel : l'utilisateur dépose un fichier dans Agent/Syntheses/, l'agent le lit.

Même économie que pour la mémoire : lister renvoie un extrait de tête, pas le
texte intégral. L'agent ouvre un document en entier seulement s'il en a besoin.
"""
from pathlib import Path

from django.conf import settings

DOCS_DIR = Path(settings.BASE_DIR) / 'Agent' / 'Syntheses'
# Un brief ou une note arrive naturellement en Word ou en PDF : ne lire que
# du texte brut obligeait à une conversion manuelle, donc à ne rien déposer.
EXTENSIONS = {'.md', '.txt', '.csv', '.docx', '.pdf'}
APERCU = 400
MAX_CARACTERES = 60_000


class DocumentError(ValueError):
    """Document introuvable — le message repart à l'agent."""


def _fichiers():
    if not DOCS_DIR.exists():
        return []
    return sorted(
        (c for c in DOCS_DIR.rglob('*')
         if c.is_file() and c.suffix.lower() in EXTENSIONS
         and not c.name.startswith('LISEZ-MOI')),
        key=lambda c: c.stat().st_mtime, reverse=True,
    )


def _cle(chemin):
    return str(chemin.relative_to(DOCS_DIR))


def _texte(chemin):
    """Extrait le texte d'un document, quel que soit son format."""
    suffixe = chemin.suffix.lower()

    if suffixe == '.docx':
        from docx import Document
        doc = Document(chemin)
        morceaux = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for rang in table.rows:
                cellules = [c.text.strip() for c in rang.cells]
                if any(cellules):
                    morceaux.append(' | '.join(cellules))
        return '\n'.join(morceaux)

    if suffixe == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                return "[PDF illisible : installer pypdf (pip install pypdf)]"
        return '\n'.join((page.extract_text() or '') for page in PdfReader(chemin).pages)

    return chemin.read_text(encoding='utf-8', errors='replace')


def lister():
    """Inventaire des documents déposés, du plus récemment modifié au plus ancien."""
    import datetime as dt

    fichiers = _fichiers()
    if not fichiers:
        return {'documents': [],
                'note': "Aucune synthèse déposée. Le dossier Agent/Syntheses/ existe "
                        "mais est vide : n'invente pas son contenu, et ne le signale "
                        "que si la mission portait dessus."}

    return {'documents': [{
        'document': _cle(c),
        'modifie': dt.datetime.fromtimestamp(c.stat().st_mtime).strftime('%Y-%m-%d'),
        'taille': c.stat().st_size,
        'apercu': _texte(c)[:APERCU].strip(),
    } for c in fichiers]}


def lire(document):
    """Renvoie le texte intégral d'un document."""
    index = {_cle(c): c for c in _fichiers()}
    if document not in index:
        raise DocumentError(
            f"Document '{document}' introuvable. Disponibles : "
            f"{', '.join(sorted(index)) or 'aucun'}."
        )
    texte = _texte(index[document])
    tronque = len(texte) > MAX_CARACTERES
    return {
        'document': document,
        'tronque': tronque,
        'contenu': texte[:MAX_CARACTERES] + ('\n\n[…document tronqué]' if tronque else ''),
    }
