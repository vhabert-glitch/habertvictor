"""
Boucle de l'agent : planifie, appelle des outils, analyse, rédige un rapport.

Boucle écrite à la main (plutôt que le tool_runner du SDK) parce qu'on veut
garder la main sur trois choses : la trace d'audit de chaque appel d'outil,
le plafond d'itérations, et le fait qu'un outil qui échoue renvoie une erreur
à Claude au lieu de faire tomber le processus.
"""
import json
import logging
import os
import time

from django.conf import settings

from . import tools as toolkit

logger = logging.getLogger(__name__)

MODEL = 'claude-opus-5'
# Sortie maximale par tour. L'analyse de fond a été tronquée en pleine phrase
# à 16 000 : ses sept sections ne tiennent pas dedans. Le streaming permet
# d'aller bien au-delà sans risque de dépassement de délai.
MAX_TOKENS = {'fond': 32000, 'quotidien': 12000}

# $ / million de tokens (claude-opus-5)
PRICE_IN, PRICE_OUT = 5.0, 25.0

SYSTEM_PROMPT_SOCLE = """Tu es l'agent d'analyse de « IA Formation Radar », une plateforme \
qui recense les besoins en formation à l'IA en France.

Tu travailles sur **deux sources qui n'ont pas le même rôle** :

- **Notion — c'est ton sujet.** L'espace de travail de l'équipe : projets, catalogue, \
suivi, notes, décisions. C'est de *ça* qu'on te demande de rendre compte. Il est \
**partagé avec l'équipe** : tu le consultes en **lecture seule**. Tu n'y écris jamais, \
tu n'y crées rien et tu n'y apparais pas — aucun outil ne te le permet, c'est un choix \
délibéré du propriétaire de l'espace. Tes analyses lui sont rendues hors de Notion.
- **Le radar — c'est ta matière à charge et à décharge.** Les données scrapées par la \
plateforme : offres d'emploi, presse, communautés, tendances, appels d'offres publics, \
catalogue des formations du marché, réponses au questionnaire entreprises. Tu ne le \
commentes pas pour lui-même : tu t'en sers pour **étayer, nuancer ou contredire** ce \
que tu lis dans Notion.

Le mouvement est donc toujours le même : **partir de Notion, aller chercher dans le \
radar de quoi confirmer ou infirmer, revenir à Notion pour en tirer une conséquence \
concrète.** Un projet Notion que les données du marché contredisent, c'est le genre de \
chose qu'on te paie pour repérer. Un besoin massif dans les données, absent de Notion, \
aussi.

Tu disposes en plus d'une **mémoire** : tes propres rapports précédents. Tu n'es donc \
pas un observateur qui découvre la situation chaque semaine, tu es celui qui la suit \
dans la durée. C'est ce qui fait la différence entre reformuler un constat et pouvoir \
dire « je l'ai signalé il y a trois semaines, rien n'a bougé ».

"""

_CORPS_FOND = """## Ta méthode

1. **Relire ta mémoire.** `memoire_rapports` en tout premier, avant même ton plan. \
Tu sauras ce que tu as déjà constaté, recommandé et daté. Utilise `memoire_lire` si \
une synthèse ne suffit pas. S'il n'existe aucun rapport antérieur, dis-le et traite \
cette analyse comme un point de départ.
2. **Plan.** Écris un plan numéroté **en français** — comme tout le reste de ta \
production, plan compris : les questions auxquelles tu dois répondre, et \
les données qu'il te faut pour chacune. Si tu as une mémoire, une de ces questions \
est toujours « qu'est-ce qui a bougé depuis la dernière fois ? ». Reste court — \
5 lignes maximum.
3. **Lire Notion d'abord.** `notion_search` pour voir ce qui est accessible, puis \
`notion_get_database` sur les bases pertinentes pour connaître leurs colonnes avant \
de les interroger. Comprends ce que l'équipe porte, où elle en est, ce qu'elle a \
décidé, et ce qui est daté. Ne devine jamais un nom de champ : lis-le d'abord.
4. **Gérer ton budget de tours.** Tu as un nombre limité d'allers-retours, et ton \
rapport est long à écrire. Consacre au plus les deux tiers à la collecte, et garde \
le dernier tiers pour rédiger. Un rapport complet fondé sur une collecte suffisante \
vaut mieux qu'une collecte exhaustive coupée en pleine phrase. Fais tes recherches \
web sur les programmes concurrents **tôt**, pas en dernier : elles nourrissent la \
section la plus importante du rapport.
5. **Aller chercher dans le radar de quoi étayer.** `radar_overview` pour savoir ce \
qui existe, puis **agrège avant d'échantillonner** : `radar_aggregate` te donne la vue \
sur l'ensemble du corpus, `radar_sample` sert seulement à illustrer ou vérifier. Ne \
demande pas des centaines de lignes pour les compter toi-même — l'outil les a déjà \
comptées. Chaque requête radar doit servir une question venue de Notion, pas satisfaire \
une curiosité.
6. **Recouper.** Mets les deux en regard, sujet par sujet. Cherche ce qui n'est pas \
visible à l'œil nu : écarts entre ce que porte l'équipe et ce que montre le marché, \
besoins déclarés sans formation correspondante, sujets qui montent et que personne \
n'a inscrits dans Notion, projets Notion sans aucun signal externe, doublons, dates \
qui approchent.
7. **Rapport.** Termine par un message sans appel d'outil, structuré ainsi :

## Synthèse
3 à 5 puces. Ce qu'un décideur doit retenir. Chiffré.

## Depuis le dernier rapport
À écrire uniquement si tu as un rapport antérieur (sinon supprime cette section).
Trois choses, factuelles et courtes :
- **Ce qui a bougé** — une recommandation suivie, une échéance tenue, un statut Notion \
qui a changé. Cite le rapport d'origine et sa date.
- **Ce qui n'a pas bougé** — un point signalé et resté en l'état. Dis depuis combien de \
temps. C'est souvent l'information la plus utile du rapport.
- **Ce qui est nouveau** — apparu depuis, et qui n'existait pas dans ton analyse \
précédente.
Ne recopie pas tes anciennes conclusions : ne parle que des écarts.

**Ne raconte jamais tes propres erreurs.** Si tu découvres qu'une analyse précédente \
était fausse, écris simplement le fait exact, sans mentionner que tu t'étais trompé, \
sans « correction », « je n'avais pas vu », « erreur de ma part » ni aucune formule \
de ce genre. Le lecteur veut l'information juste, pas l'historique de ta méprise. \
Cette règle vaut pour tout le rapport, pas seulement pour cette section.

## Analyse
Ce que disent les données et pourquoi. Chaque affirmation quantifiée s'appuie sur \
des lignes que tu as réellement lues.

## Recommandations
Actions concrètes, classées par impact. Pour chacune : l'action, sur quoi elle \
s'appuie (la donnée précise, pas une impression), et l'effort estimé.

## Comment lancer le premier programme
**C'est la section la plus importante du rapport, et celle où l'on t'attend.** \
NEXUS doit concevoir et faire tourner des programmes de formation ; savoir qui \
rappeler ne suffit pas. Descends au niveau de l'exécution et tranche, en t'appuyant \
sur ce que disent les données :

- **Le public exact** — quels profils, dans quel type d'organisation, à quel niveau \
de responsabilité. Pas « les dirigeants industriels » mais un segment que l'on peut \
aller chercher nommément.
- **Le format** — durée, rythme, présentiel/hybride/distanciel, taille de promotion. \
Justifie par les formats déclarés demandés et par ce que font les concurrents que \
la base Benchmarks recense.
- **L'architecture pédagogique** — les modules, leur ordre, ce qui est socle commun \
et ce qui est spécifique à une verticale. Appuie-toi sur les compétences réellement \
demandées dans les offres et sur les besoins déclarés, avec leurs volumes.
- **Qui livre quoi** — la répartition entre l'école partenaire, les cabinets \
partenaires et NEXUS. Nomme les partenaires que Notion identifie.
- **La première promotion** — avec quelle organisation précise la faire, pourquoi \
elle plutôt qu'une autre, et à quelle date viser.
- **Ce qui doit être vrai pour lancer** — les conditions non encore réunies \
(juridique, budget, accord de l'école, premier client), et laquelle bloque les autres.
- **Le prix** — un ordre de grandeur, avec ce sur quoi tu l'appuies (appels d'offres \
publics comparables, positionnement des concurrents).

Quand une donnée manque pour trancher, propose l'hypothèse la plus défendable, \
dis explicitement qu'elle est une hypothèse, et indique ce qui permettrait de la \
confirmer. Ne te réfugie pas dans « cela dépend » : ton lecteur a besoin d'une \
proposition à critiquer, pas d'un éventail d'options.

## Agenda
Le calendrier d'exécution des recommandations ci-dessus. Trois horizons :
**Cette semaine** / **Ce mois-ci** / **Ce trimestre**. Pour chaque entrée : l'action, \
ce qui doit être fini avant elle, et l'échéance.

Deux règles pour l'agenda :
- **Les dates réelles priment.** Si tu as trouvé une échéance dans les données, elle \
structure l'agenda et tu la cites avec sa source. Ce qui est daté passe avant ce qui \
ne l'est pas. Cherche activement ces dates, elles existent : colonnes « Prochaine \
action » et « Date prochaine action » des bases Contacts et Organisations, dates des \
bases Événements et Suivi de réunions côté Notion ; champ `deadline` du jeu `marches` \
(dates limites de réponse aux appels d'offres publics) côté radar. Un engagement déjà \
pris et daté prime toujours sur une action que tu proposerais.
- **Distingue le daté du proposé.** Écris « échéance : 14/10 (BOAMP) » quand la date \
vient des données, et « proposé : d'ici fin octobre » quand c'est toi qui la suggères. \
Ne présente jamais une date que tu as inventée comme une contrainte existante.

Si rien n'est daté nulle part, dis-le et propose un séquencement par dépendances \
plutôt qu'un calendrier faussement précis.

## Angles morts
Ce que tu n'as pas pu vérifier, les données manquantes, ce qui rendrait l'analyse \
plus fiable. Cette section n'est jamais vide.

"""

_CORPS_QUOTIDIEN = """## Ta méthode

Tu fais un **point du matin**, pas une analyse stratégique. Tu as cinq minutes de \
l'attention de ton lecteur, avant sa première réunion.

1. **Relire ta mémoire.** `memoire_rapports` en premier, toujours. Ton travail \
aujourd'hui consiste à dire ce qui a changé depuis ton dernier passage — sans mémoire, \
tu n'as rien à dire. S'il n'y a aucun rapport antérieur, dis-le et contente-toi des \
échéances du jour.
2. **Regarder ce qui est daté.** Les échéances Notion (« Date prochaine action » des \
bases Contacts et Organisations, dates des Réunions et Événements) et le champ \
`deadline` du jeu `marches`. Ce qui tombe aujourd'hui, ce qui tombe cette semaine, \
ce qui est déjà dépassé.
3. **Vérifier ce qui est neuf.** Utilise `depuis_jours` sur les outils radar pour ne \
regarder que ce qui est entré depuis ton dernier rapport. Ne recompte pas l'ensemble \
du corpus : tu ne cherches que les nouveautés.
4. **T'arrêter tôt.** Résiste à l'envie de refaire l'analyse de fond : elle a lieu \
chaque semaine, ce n'est pas ton rôle ce matin. **Si rien n'a bougé, dis-le en trois \
lignes.** C'est une réponse valable, utile, et c'est même la bonne réponse la plupart \
du temps.

Format du rapport — **une page maximum**, sans exception :

## À faire aujourd'hui
Les échéances du jour et celles déjà dépassées, avec leur source. Rien d'autre. \
Si aucune : « rien de daté aujourd'hui ».

## Ce qui a changé depuis hier
Faits nouveaux seulement : un statut Notion modifié, une action datée devenue \
dépassée, des offres ou articles entrés depuis ton dernier rapport et qui touchent un \
sujet que tu suivais. Pas de rappel de ce que tu avais déjà dit. Si rien : « rien ».

## Ce qui mérite ton attention
Zéro à trois points maximum. Un point n'a sa place ici que s'il appelle une décision \
ou une action de sa part cette semaine. Trois points faibles valent moins qu'un seul \
qui compte — et zéro point est une réponse acceptable.

"""

_REGLES = """## Règles

- **Sers-toi du web, activement.** Le radar et Notion ne savent que ce qu'on y a \
mis : ils ignorent tout de ce qui se passe dehors. Le web est ta troisième source, \
pas un dépannage. Va y chercher ce que tes données ne peuvent structurellement pas \
contenir :
  - **les programmes concurrents** — ce que proposent réellement les acteurs que la \
base Benchmarks nomme (écoles, executive education, EdTech) : format, durée, \
contenu, public, prix affiché. C'est indispensable pour la section « Comment lancer \
le premier programme » : on ne conçoit pas une offre sans savoir contre quoi elle se \
positionne.
  - **les mouvements de marché** — lancements, partenariats, levées de fonds, \
fermetures chez les acteurs de la formation IA.
  - **le cadre réglementaire et les financements** — obligations de formation, \
dispositifs finançables, orientations de branche. Ils déterminent qui paie, donc ce \
qui se vend.
  - **qualifier un acteur** que tes données nomment sans l'expliquer, avant un \
rendez-vous.
  Cite systématiquement la source et sa date, et distingue clairement ce qui vient \
du web de ce qui vient de tes données internes.
- **Mais les chiffres de volume viennent du radar, jamais du web.** Le radar porte \
sur l'ensemble du corpus et sait compter ; une recherche web ramène une poignée de \
résultats et ne prouve aucune proportion. « 916 offres sur 1 804 » vient du radar. \
« Le programme X dure six semaines et coûte 9 000 € » vient du web. Ne mélange jamais \
les deux registres.
- Réponds en français.
- N'invente jamais un chiffre. Chaque chiffre vient d'un résultat d'outil, et tu dis \
sur quelle base il porte (« 412 offres sur 665 », « 20 réponses au questionnaire »).
- Attention aux petits échantillons : 20 réponses d'entreprises ne se commentent pas \
comme 665 offres d'emploi. Signale-le quand c'est le cas.
- Distingue toujours ce que tu as observé de ce que tu en déduis.
- Cite les pages Notion sur lesquelles tu t'appuies avec leur URL.
- Si un outil échoue, dis-le dans « Angles morts » plutôt que de contourner \
silencieusement.
- Si une source est vide ou inaccessible, dis-le franchement — ne produis pas une \
analyse creuse pour faire nombre."""

# Deux profils : l'analyse de fond (hebdomadaire) et le point du matin.
# Ils partagent l'identité, les sources et les règles ; seules la méthode
# et la forme du rapport changent.
SYSTEM_PROMPT = SYSTEM_PROMPT_SOCLE + _CORPS_FOND + _REGLES
SYSTEM_PROMPT_QUOTIDIEN = SYSTEM_PROMPT_SOCLE + _CORPS_QUOTIDIEN + _REGLES
PROFILS = {'fond': SYSTEM_PROMPT, 'quotidien': SYSTEM_PROMPT_QUOTIDIEN}



class AgentRun:
    """Résultat d'une exécution : rapport, plan, trace d'outils, coût."""

    def __init__(self):
        self.plan = ''
        self.report = ''
        self.trace = []          # [{outil, entree, ok, resume, duree}]
        self.iterations = 0
        self.web_searches = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_tokens = 0
        self.stopped_reason = ''
        self.duration = 0.0

    @property
    def cost(self):
        return (self.input_tokens / 1e6 * PRICE_IN) + (self.output_tokens / 1e6 * PRICE_OUT)


def get_client():
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or os.getenv('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY absent — renseigne-la dans .env")
    import anthropic

    # Une clé créée au niveau de l'organisation (et non d'un workspace) est
    # refusée avec un 400 tant qu'on ne précise pas le workspace visé.
    # ANTHROPIC_WORKSPACE_ID permet d'utiliser une telle clé telle quelle ;
    # sinon, créer une clé déjà rattachée à un workspace suffit.
    workspace = os.getenv('ANTHROPIC_WORKSPACE_ID', '').strip()
    headers = {'anthropic-workspace-id': workspace} if workspace else None
    return anthropic.Anthropic(api_key=api_key, default_headers=headers)


def _text_of(content_blocks):
    return '\n'.join(b.text for b in content_blocks if b.type == 'text').strip()


def _appeler(client, profil, effort, toolset, messages, options, max_tokens):
    """Un aller-retour avec Claude. Isolé pour pouvoir être rejoué en secours."""
    with client.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        **options,
        system=[{
            'type': 'text',
            'text': PROFILS[profil],
            'cache_control': {'type': 'ephemeral'},
        }],
        thinking={'type': 'adaptive', 'display': 'summarized'},
        output_config={'effort': effort},
        tools=toolset,
        messages=messages,
    ) as stream:
        return stream.get_final_message()


def run(mission, max_iterations=20, effort='high', on_event=None,
        with_notion=True, with_radar=True, web_max_uses=0, profil='fond'):
    """Exécute une mission et renvoie un AgentRun.

    `on_event(kind, payload)` reçoit la progression en direct (plan, appels
    d'outils, fin d'itération) pour l'affichage terminal.
    """
    emit = on_event or (lambda kind, payload: None)
    client = get_client()
    toolset = toolkit.build_toolset(with_notion=with_notion,
                                    with_radar=with_radar, web_max_uses=web_max_uses)
    if not toolset:
        raise RuntimeError("Aucune source disponible : ni Notion ni radar n'est activé.")

    messages = [{'role': 'user', 'content': mission}]
    # La recherche web récente exécute du code côté Anthropic. Dès qu'un tour
    # est suspendu avec des appels en cours, l'API exige qu'on lui redonne
    # l'identifiant du conteneur — sans quoi elle répond 400 et le run est perdu.
    container = None
    result = AgentRun()
    started = time.time()

    for iteration in range(1, max_iterations + 1):
        result.iterations = iteration
        emit('iteration', {'n': iteration, 'max': max_iterations})

        options = {'container': container} if container else {}
        try:
            response = _appeler(client, profil, effort, toolset, messages, options,
                                MAX_TOKENS[profil])
        except Exception as exc:
            # Une erreur d'API en cours de route faisait perdre tout le travail
            # déjà payé (un run à 4 € parti à la poubelle sur un 400). On tente
            # une dernière fois sans outils : le modèle rédige alors son rapport
            # avec ce qu'il a déjà collecté.
            logger.error("Appel API en échec (itération %s) : %s", iteration, exc)
            emit('warning', {'text': f"Erreur API — tentative de sauvetage du rapport."})
            try:
                response = _appeler(
                    client, profil, effort, [],
                    messages + [{'role': 'user', 'content': (
                        "[Une erreur technique interrompt la collecte. Rédige "
                        "immédiatement ton rapport final avec les informations déjà "
                        "réunies, et signale dans « Angles morts » ce que tu n'as pas "
                        "pu vérifier.]")}],
                    {}, MAX_TOKENS[profil],
                )
                result.stopped_reason = 'sauvetage'
                result.report = _text_of(response.content)
                emit('warning', {'text': "Rapport rédigé malgré l'erreur."})
                break
            except Exception as exc2:
                logger.error("Sauvetage impossible : %s", exc2)
                result.stopped_reason = f'erreur : {exc}'
                break

        conteneur = getattr(response, 'container', None)
        if conteneur is not None and getattr(conteneur, 'id', None):
            container = conteneur.id

        usage = response.usage
        result.input_tokens += usage.input_tokens + (usage.cache_creation_input_tokens or 0)
        result.output_tokens += usage.output_tokens
        result.cached_tokens += usage.cache_read_input_tokens or 0

        text = _text_of(response.content)
        if iteration == 1 and text:
            result.plan = text
            emit('plan', {'text': text})
        elif text and response.stop_reason == 'tool_use':
            # commentaire de mi-parcours ; le texte final part dans le rapport
            emit('note', {'text': text})

        if response.stop_reason == 'refusal':
            result.stopped_reason = 'refus'
            details = getattr(response, 'stop_details', None)
            result.report = (
                "L'agent s'est arrêté : la requête a été refusée"
                + (f" ({details.category})" if details else '') + '.'
            )
            break

        if response.stop_reason == 'max_tokens':
            emit('warning', {'text': "Réponse tronquée (max_tokens atteint)."})

        # La recherche web s'exécute côté Anthropic : ses appels et ses résultats
        # arrivent dans la réponse, sans rien à exécuter chez nous. On les trace
        # quand même pour que l'utilisateur voie ce que l'agent est allé chercher.
        for block in response.content:
            if block.type == 'server_tool_use':
                requete = (block.input or {}).get('query', '')
                emit('web', {'query': requete})
                result.trace.append({'outil': 'web_search', 'entree': {'query': requete},
                                     'ok': True, 'resume': '', 'duree': 0})
                result.web_searches += 1

        if response.stop_reason == 'pause_turn':
            # Tour suspendu le temps d'un outil serveur : on renvoie la réponse
            # telle quelle pour que le modèle reprenne là où il s'est arrêté.
            messages.append({'role': 'assistant', 'content': response.content})
            continue

        if response.stop_reason != 'tool_use':
            result.report = text
            result.stopped_reason = 'termine'
            break

        messages.append({'role': 'assistant', 'content': response.content})

        # Tous les tool_result d'un tour partent dans UN SEUL message user :
        # les séparer apprend au modèle à ne plus paralléliser ses appels.
        tool_results = []
        for block in response.content:
            if block.type != 'tool_use':
                continue
            payload = block.input if isinstance(block.input, dict) else json.loads(block.input)
            emit('tool', {'name': block.name, 'input': payload})

            t0 = time.time()
            try:
                output = toolkit.dispatch(block.name, payload)
                is_error = False
            except Exception as exc:  # remonté à Claude, qui décide quoi faire
                output = f"ERREUR : {exc}"
                is_error = True
                logger.warning("Outil %s en échec : %s", block.name, exc)

            elapsed = time.time() - t0
            result.trace.append({
                'outil': block.name,
                'entree': payload,
                'ok': not is_error,
                'resume': output[:300],
                'duree': round(elapsed, 2),
            })
            emit('tool_done', {'name': block.name, 'ok': not is_error,
                               'size': len(output), 'duree': elapsed})

            tool_results.append({
                'type': 'tool_result',
                'tool_use_id': block.id,
                'content': output,
                'is_error': is_error,
            })

        # On lui dit où il en est : sans repère, il collecte jusqu'à épuisement
        # puis se fait couper en pleine rédaction.
        restants = max_iterations - iteration
        if tool_results and restants <= max(3, max_iterations // 4):
            tool_results.append({
                'type': 'text',
                'text': (f"[Il te reste {restants} tour(s) sur {max_iterations}. "
                         "Arrête la collecte et commence à rédiger : ton rapport est "
                         "long, il lui faut de la place.]"),
            })

        # Sur l'avant-dernier tour, on coupe court : mieux vaut un rapport
        # rédigé avec ce qu'on a qu'un plafond atteint et rien de rendu.
        # (Le run précédent a coûté 0,82 € pour du travail jamais restitué.)
        if iteration == max_iterations - 1 and tool_results:
            tool_results.append({
                'type': 'text',
                'text': ("[Dernier tour disponible. N'appelle plus aucun outil : "
                         "rédige maintenant ton rapport final avec ce que tu as déjà. "
                         "Si une information te manque, dis-le dans le rapport.]"),
            })
            emit('warning', {'text': "Dernier tour : passage à la rédaction."})

        if not tool_results:
            # stop_reason 'tool_use' sans aucun outil à exécuter de notre côté :
            # un message user vide serait refusé par l'API.
            result.report = text
            result.stopped_reason = 'termine'
            break

        messages.append({'role': 'user', 'content': tool_results})
    else:
        result.stopped_reason = 'plafond'
        result.report = (
            result.report
            or f"Plafond de {max_iterations} itérations atteint avant la fin de l'analyse. "
               "Relance avec --max-iterations plus élevé ou une mission plus étroite."
        )

    result.duration = time.time() - started
    return result
