"""
Lance l'agent d'analyse sur la base Notion.

    python manage.py agent_run --check
    python manage.py agent_run "Quelles formations IA manquent à notre catalogue ?"
    python manage.py agent_run "Fais le point sur le pipeline" --effort max
"""
import datetime as dt
import json
import textwrap
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.agent import brain, notion, radar

ESPACE = Path(settings.BASE_DIR) / 'Agent'
# Un dossier par type : mélangés, sept points du jour par semaine noyaient
# l'analyse de fond du lundi.
DOSSIERS = {
    'Analyse de fond': ESPACE / 'Rapports',
    'Point du jour': ESPACE / 'Points du jour',
}
# Le markdown est le format de travail (mémoire de l'agent) : il est rangé
# à l'écart pour que les dossiers de lecture ne contiennent que des .docx.
MEMOIRE_DIR = ESPACE / 'Technique' / 'memoire'

_JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']


class Command(BaseCommand):
    help = "Agent d'analyse : lit la base Notion, en tire une synthèse et des recommandations."

    def add_arguments(self, parser):
        parser.add_argument(
            'mission', nargs='?', default=None,
            help="Ce que l'agent doit analyser. Par défaut : bilan général.",
        )
        parser.add_argument(
            '--quotidien', action='store_true',
            help="Point du matin : une page, ce qui a changé et ce qui tombe aujourd'hui. "
                 "Bien moins cher que l'analyse de fond (défauts : effort medium, "
                 "12 itérations, 2 recherches web).",
        )
        parser.add_argument(
            '--check', action='store_true',
            help="Vérifie la configuration et liste ce que Notion expose. N'appelle pas Claude.",
        )
        parser.add_argument(
            '--effort', default=None, choices=['low', 'medium', 'high', 'xhigh', 'max'],
            help="Profondeur de réflexion. Défaut : high en analyse de fond, "
                 "medium en point quotidien. 'max' pour les arbitrages difficiles.",
        )
        parser.add_argument(
            '--max-iterations', type=int, default=None,
            help="Plafond d'allers-retours outils. Défaut : 20 en analyse de fond, "
                 "12 en point quotidien.",
        )
        parser.add_argument(
            '--only', default=None, choices=['notion', 'radar'],
            help="Restreindre l'agent à une seule source. Par défaut il a les deux.",
        )
        parser.add_argument(
            '--web', type=int, default=None, metavar='N',
            help="Nombre max de recherches web par run (0 = désactivé). Défaut 6. "
                 "Défaut : 14 en analyse de fond, 2 en point du jour.",
        )
        parser.add_argument(
            '--out', default=None,
            help="Chemin du rapport. Défaut : Agent/Rapports/AAAA-MM-JJ-HHMM.md",
        )
        parser.add_argument(
            '--quiet', action='store_true',
            help="N'affiche que le rapport final.",
        )

    # ── affichage ────────────────────────────────────────────

    def _rule(self, title=''):
        self.stdout.write(self.style.HTTP_INFO(f"\n{'─' * 70}"))
        if title:
            self.stdout.write(self.style.HTTP_INFO(f"  {title}"))
            self.stdout.write(self.style.HTTP_INFO('─' * 70))

    def _make_reporter(self, quiet):
        def report(kind, payload):
            if quiet:
                return
            if kind == 'iteration':
                self.stdout.write(self.style.HTTP_INFO(
                    f"\n▸ itération {payload['n']}/{payload['max']}"))
            elif kind == 'plan':
                self._rule('PLAN')
                self.stdout.write(payload['text'])
            elif kind == 'note':
                self.stdout.write(textwrap.indent(payload['text'], '  '))
            elif kind == 'tool':
                args = json.dumps(payload['input'], ensure_ascii=False)
                self.stdout.write(f"  → {payload['name']}({args[:110]})")
            elif kind == 'tool_done':
                mark = '✓' if payload['ok'] else '✗'
                style = self.style.SUCCESS if payload['ok'] else self.style.ERROR
                self.stdout.write(style(
                    f"  {mark} {payload['size']} caractères en {payload['duree']:.1f}s"))
            elif kind == 'warning':
                self.stdout.write(self.style.WARNING(f"  ! {payload['text']}"))
        return report

    # ── modes ────────────────────────────────────────────────

    def _check(self):
        self._rule('VÉRIFICATION')
        key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        self.stdout.write(
            self.style.SUCCESS("✓ ANTHROPIC_API_KEY présente") if key
            else self.style.ERROR("✗ ANTHROPIC_API_KEY absente (.env)")
        )
        try:
            import anthropic  # noqa: F401
            self.stdout.write(self.style.SUCCESS("✓ package anthropic installé"))
        except ImportError:
            self.stdout.write(self.style.ERROR("✗ pip install anthropic"))

        self._rule('DONNÉES DU RADAR')
        inventaire = radar.overview()
        for nom, meta in inventaire.items():
            periode = meta.get('periode')
            fenetre = f" — {periode['debut']} → {periode['fin']}" if periode else ''
            self.stdout.write(f"  {nom:12} {meta['lignes']:>6} ligne(s){fenetre}")
            self.stdout.write(self.style.HTTP_INFO(
                f"               agrégeable par : {', '.join(meta['grouper_par'])}"))

        self._rule('NOTION')
        if not notion.is_configured():
            self.stdout.write(self.style.WARNING(
                "! NOTION_API_KEY absente (.env) — l'agent tournera sur le radar seul."))
            return
        self.stdout.write(self.style.SUCCESS("✓ NOTION_API_KEY présente"))

        try:
            items = notion.search(page_size=100)
        except notion.NotionError as exc:
            self.stdout.write(self.style.ERROR(f"✗ Notion : {exc}"))
            return

        databases = [i for i in items if i['type'] == 'database']
        pages = [i for i in items if i['type'] == 'page']
        self.stdout.write(self.style.SUCCESS(
            f"✓ Notion accessible : {len(databases)} base(s), {len(pages)} page(s)"))

        if not items:
            self.stdout.write(self.style.WARNING(
                "\n  Rien n'est partagé avec l'intégration. Dans Notion, ouvre la page "
                "ou la base → ••• → Connexions → ajoute ton intégration."))
            return

        for db in databases:
            self.stdout.write(f"\n  📊 {db['titre'] or '(sans titre)'}")
            self.stdout.write(f"     id: {db['id']}")
            try:
                schema = notion.get_database(db['id'])
                cols = ', '.join(f"{n} ({m['type']})" for n, m in schema['colonnes'].items())
                self.stdout.write(f"     colonnes: {textwrap.shorten(cols, 300)}")
            except notion.NotionError as exc:
                self.stdout.write(self.style.WARNING(f"     schéma illisible : {exc}"))
        for page in pages[:15]:
            self.stdout.write(f"  📄 {page['titre'] or '(sans titre)'} — {page['id']}")

    def _save(self, run, mission, path, libelle='Rapport'):
        path.parent.mkdir(parents=True, exist_ok=True)
        trace = '\n'.join(
            f"- `{t['outil']}` {'✓' if t['ok'] else '✗'} ({t['duree']}s) — "
            f"`{json.dumps(t['entree'], ensure_ascii=False)[:160]}`"
            for t in run.trace
        ) or '- aucun appel'

        # le plan commence souvent déjà par son propre titre « ## Plan »
        plan = run.plan.strip()
        if plan.lower().startswith('## plan'):
            plan = plan.split('\n', 1)[1].strip() if '\n' in plan else ''

        path.write_text(
            f"# {libelle} — {_JOURS[dt.datetime.now().weekday()]} "
            f"{dt.datetime.now():%d/%m/%Y}, {dt.datetime.now():%Hh%M}\n\n"
            f"**Mission :** {mission}\n\n"
            f"---\n\n## Plan\n\n{plan or '(non explicité)'}\n\n"
            f"---\n\n{run.report}\n\n"
            f"---\n\n## Trace d'exécution\n\n{trace}\n\n"
            f"*{run.iterations} itération(s), {run.duration:.0f}s, "
            f"{run.input_tokens:,} tokens en entrée / {run.output_tokens:,} en sortie "
            f"({run.cached_tokens:,} lus en cache), ~${run.cost:.3f} — fin : {run.stopped_reason}*\n",
            encoding='utf-8',
        )
        return path

    # ── point d'entrée ───────────────────────────────────────

    def handle(self, *args, **options):
        if options['check']:
            self._check()
            return

        quotidien = options['quotidien']
        profil = 'quotidien' if quotidien else 'fond'

        # Le point du matin est volontairement bridé : c'est ce qui le rend
        # tenable tous les jours. L'analyse de fond, elle, a le droit de creuser.
        effort = options['effort'] or ('medium' if quotidien else 'high')
        max_iter = options['max_iterations'] or (12 if quotidien else 20)
        web = options['web'] if options['web'] is not None else (2 if quotidien else 14)

        if quotidien:
            mission = options['mission'] or (
                "Fais le point du matin. Qu'est-ce qui a changé depuis ton dernier "
                "rapport, qu'est-ce qui tombe aujourd'hui ou est déjà dépassé, et "
                "qu'est-ce qui mérite mon attention aujourd'hui ? Sois bref."
            )
        else:
            mission = options['mission'] or (
                "Prends connaissance de ce que porte l'équipe dans Notion, recoupe-le "
                "avec les données du radar, et dis-moi : ce qu'il faut retenir, où sont "
                "les écarts entre ce qu'on porte et ce que montre le marché, ce que tu "
                "recommandes, et dans quel ordre l'exécuter."
            )

        with_notion = options['only'] != 'radar'
        with_radar = options['only'] != 'notion'

        if with_notion and not notion.is_configured():
            if options['only'] == 'notion':
                raise CommandError(
                    "NOTION_API_KEY absente. Lance `python manage.py agent_run --check` "
                    "pour le détail de la configuration."
                )
            self.stdout.write(self.style.WARNING(
                "  NOTION_API_KEY absente — l'agent tourne sur le radar seul."))
            with_notion = False

        sources = ' + '.join(
            s for s, on in (('Notion', with_notion), ('radar', with_radar)) if on)

        self._rule('AGENT — IA FORMATION RADAR')
        self.stdout.write(f"  Mission : {mission}")
        self.stdout.write(f"  Sources : {sources}")
        self.stdout.write(f"  Format  : {'point quotidien' if quotidien else 'analyse de fond'}")
        self.stdout.write(f"  Effort  : {effort} · {max_iter} itérations max · {web} recherche(s) web")
        self.stdout.write("  Mode    : lecture seule (l'agent n'écrit jamais dans Notion)")

        try:
            run = brain.run(
                mission,
                max_iterations=max_iter,
                effort=effort,
                on_event=self._make_reporter(options['quiet']),
                with_notion=with_notion,
                with_radar=with_radar,
                web_max_uses=web,
                profil=profil,
            )
        except RuntimeError as exc:
            raise CommandError(str(exc))

        self._rule('RAPPORT')
        self.stdout.write(run.report or '(rapport vide)')

        # Nom lisible dans le Finder : la date d'abord pour le tri chronologique,
        # puis le type en clair. « 2026-09-07-1143-quotidien.md » ne disait rien.
        maintenant = dt.datetime.now()
        libelle = 'Point du jour' if quotidien else 'Analyse de fond'
        nom = f"{maintenant:%Y-%m-%d} - {libelle} ({maintenant:%Hh%M})"
        path = Path(options['out']) if options['out'] else MEMOIRE_DIR / f'{nom}.md'

        # Un run qui n'a rien produit ne laisse pas de fichier : un rapport vide
        # pollue le dossier et fausse la mémoire de l'agent.
        if not (run.report or '').strip():
            self._rule()
            self.stdout.write(self.style.ERROR(
                "  Aucun rapport produit — aucun fichier écrit."))
            self.stdout.write(f"  {run.iterations} itération(s) · ~${run.cost:.3f} "
                              f"· fin : {run.stopped_reason}")
            return
        self._save(run, mission, path, libelle)

        # Doublon Word : le .md est le format de travail (c'est lui que la
        # mémoire relit), le .docx est celui qui se lit.
        docx = None
        try:
            from apps.agent import word
            docx = word.convertir(path, DOSSIERS[libelle] / f'{nom}.docx')
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  Conversion Word impossible : {exc}"))

        self._rule()
        self.stdout.write(self.style.SUCCESS(f"  Rapport écrit dans {path}"))
        if docx:
            self.stdout.write(self.style.SUCCESS(f"  Version Word     : {docx.name}"))
        self.stdout.write(
            f"  {run.iterations} itération(s) · {len(run.trace)} appel(s) d'outil · "
            f"{run.duration:.0f}s · ~${run.cost:.3f}"
        )
