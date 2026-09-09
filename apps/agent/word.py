"""
Conversion des rapports markdown en documents Word lisibles.

Le markdown est le format de travail de l'agent — c'est ce que sa mémoire relit.
Mais avec ses `##` et ses `**`, il est pénible à lire pour un humain. Chaque
rapport est donc doublé d'un .docx : le .md pour la machine, le .docx pour toi.

Volontairement limité à ce que les rapports contiennent réellement : titres,
listes, gras, liens Notion, tableaux, citations. Ce n'est pas un convertisseur
markdown général.
"""
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

# **gras**, [texte](url), `code`
INLINE = re.compile(r'(\*\*.+?\*\*|\[[^\]]+\]\([^)]+\)|`[^`]+`)')
LIEN = re.compile(r'^\[([^\]]+)\]\(([^)]+)\)$')

BLEU = RGBColor(0x1A, 0x4F, 0x8B)
GRIS = RGBColor(0x60, 0x60, 0x60)


def _hyperlien(paragraphe, texte, url):
    """python-docx n'expose pas les liens : on descend dans le XML."""
    part = paragraphe.part
    r_id = part.relate_to(
        url,
        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',
        is_external=True,
    )
    from docx.oxml.shared import OxmlElement
    lien = OxmlElement('w:hyperlink')
    lien.set(qn('r:id'), r_id)

    run = OxmlElement('w:r')
    props = OxmlElement('w:rPr')
    couleur = OxmlElement('w:color')
    couleur.set(qn('w:val'), '1A4F8B')
    souligne = OxmlElement('w:u')
    souligne.set(qn('w:val'), 'single')
    props.append(couleur)
    props.append(souligne)
    run.append(props)

    t = OxmlElement('w:t')
    t.text = texte
    run.append(t)
    lien.append(run)
    paragraphe._p.append(lien)


def _ecrire_inline(paragraphe, texte):
    """Écrit du texte en gérant gras, liens et code."""
    for morceau in INLINE.split(texte):
        if not morceau:
            continue
        if morceau.startswith('**') and morceau.endswith('**'):
            paragraphe.add_run(morceau[2:-2]).bold = True
        elif morceau.startswith('`') and morceau.endswith('`'):
            run = paragraphe.add_run(morceau[1:-1])
            run.font.name = 'Menlo'
            run.font.size = Pt(9.5)
        else:
            lien = LIEN.match(morceau)
            if lien:
                _hyperlien(paragraphe, lien.group(1), lien.group(2))
            else:
                paragraphe.add_run(morceau)


def _ligne_tableau(ligne):
    return [c.strip() for c in ligne.strip().strip('|').split('|')]


def convertir(chemin_md, chemin_docx=None):
    """Transforme un rapport markdown en .docx et renvoie le chemin écrit."""
    from pathlib import Path

    chemin_md = Path(chemin_md)
    chemin_docx = Path(chemin_docx) if chemin_docx else chemin_md.with_suffix('.docx')
    lignes = chemin_md.read_text(encoding='utf-8').split('\n')

    doc = Document()
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(11)

    # La trace d'exécution et les statistiques de coût sont de la plomberie :
    # utiles dans le .md pour diagnostiquer, hors sujet dans le document qu'on lit.
    for n, ligne in enumerate(lignes):
        if ligne.strip().startswith("## Trace d'exécution"):
            lignes = lignes[:n]
            break

    i = 0
    while i < len(lignes):
        ligne = lignes[i].rstrip()

        # ── tableau ──
        if ligne.startswith('|') and i + 1 < len(lignes) and set(lignes[i + 1]) <= set('|-: '):
            entetes = _ligne_tableau(ligne)
            i += 2
            corps = []
            while i < len(lignes) and lignes[i].startswith('|'):
                corps.append(_ligne_tableau(lignes[i]))
                i += 1
            table = doc.add_table(rows=1, cols=len(entetes))
            table.style = 'Light Grid Accent 1'
            for cellule, titre in zip(table.rows[0].cells, entetes):
                cellule.text = ''
                _ecrire_inline(cellule.paragraphs[0], titre)
                for run in cellule.paragraphs[0].runs:
                    run.bold = True
            for rang in corps:
                cellules = table.add_row().cells
                for cellule, valeur in zip(cellules, rang):
                    cellule.text = ''
                    _ecrire_inline(cellule.paragraphs[0], valeur)
            doc.add_paragraph()
            continue

        if not ligne.strip() or ligne.strip() == '---':
            i += 1
            continue

        # ── titres ──
        titre = re.match(r'^(#{1,4})\s+(.*)$', ligne)
        if titre:
            niveau, texte = len(titre.group(1)), titre.group(2)
            p = doc.add_paragraph(style='Title' if niveau == 1 else f'Heading {niveau - 1}')
            _ecrire_inline(p, texte)
            i += 1
            continue

        # ── citation ──
        if ligne.startswith('>'):
            p = doc.add_paragraph(style='Intense Quote')
            _ecrire_inline(p, ligne.lstrip('> ').strip())
            i += 1
            continue

        # ── listes ──
        puce = re.match(r'^(\s*)[-*]\s+(.*)$', ligne)
        if puce:
            style = 'List Bullet' if len(puce.group(1)) < 2 else 'List Bullet 2'
            _ecrire_inline(doc.add_paragraph(style=style), puce.group(2))
            i += 1
            continue

        numero = re.match(r'^(\s*)\d+\.\s+(.*)$', ligne)
        if numero:
            _ecrire_inline(doc.add_paragraph(style='List Number'), numero.group(2))
            i += 1
            continue

        # ── ligne de statistiques en italique, en pied de rapport ──
        if ligne.startswith('*') and ligne.endswith('*') and not ligne.startswith('**'):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = p.add_run(ligne.strip('*'))
            run.italic = True
            run.font.size = Pt(9)
            run.font.color.rgb = GRIS
            i += 1
            continue

        _ecrire_inline(doc.add_paragraph(), ligne)
        i += 1

    doc.save(chemin_docx)
    return chemin_docx
