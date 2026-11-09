#!/bin/bash
# ═══════════════════════════════════════════════════════
#  Agent NEXUS — exécution du matin
#  Lundi   : analyse de fond (complète, ~4,50 €)
#  Autres  : point du jour   (une page,  ~0,35 €)
#  Déclenché par launchd à 7h30, après les scrapers de 7h00.
# ═══════════════════════════════════════════════════════

PROJECT_DIR="/Users/habertvictor/ia-formation-radar"
PYTHON="/usr/bin/python3"
LOG="$PROJECT_DIR/Agent/Technique/execution.log"

cd "$PROJECT_DIR" || exit 1

# launchd déclenche au réveil de la machine, souvent avant que le Wi-Fi soit
# associé : trois runs ont été perdus sur « Connection error » à l'itération 1.
# On attend le réseau jusqu'à 10 minutes avant de commencer.
ATTENTE=0
until curl -s --max-time 5 -o /dev/null https://api.anthropic.com/v1/models; do
    [ $ATTENTE -ge 600 ] && break
    sleep 20
    ATTENTE=$((ATTENTE + 20))
done
mkdir -p "$PROJECT_DIR/Agent/Rapports" "$PROJECT_DIR/Agent/Points du jour" "$PROJECT_DIR/Agent/Technique"

# %u : 1 = lundi … 7 = dimanche
if [ "$(date +%u)" -eq 1 ]; then
    FORMAT="analyse de fond"
    ARGS=""
else
    FORMAT="point du jour"
    ARGS="--quotidien"
fi

# La sortie complète part dans un fichier temporaire : elle contient le rapport
# entier, déjà sauvegardé à côté. On ne garde dans le journal qu'une ligne si
# tout va bien, et le détail seulement en cas d'échec — là il est utile.
BRUT=$(mktemp)
AVANT=$(find "$PROJECT_DIR/Agent" -name "*.docx" -newermt "today" 2>/dev/null | wc -l)

$PYTHON manage.py agent_run $ARGS --quiet > "$BRUT" 2>&1
CODE=$?

APRES=$(find "$PROJECT_DIR/Agent" -name "*.docx" -newermt "today" 2>/dev/null | wc -l)
DERNIER=$(find "$PROJECT_DIR/Agent/Rapports" "$PROJECT_DIR/Agent/Points du jour" \
          -name "*.docx" -newermt "-20 minutes" 2>/dev/null | head -1)

if [ $CODE -eq 0 ] && [ -n "$DERNIER" ]; then
    COUT=$(grep -o '~\$[0-9.]*' "$BRUT" | tail -1)
    echo "$(date '+%d/%m/%Y %H:%M')  ✓  $FORMAT  →  $(basename "$DERNIER")  $COUT" >> "$LOG"
    osascript -e "display notification \"$FORMAT prêt dans Agent NEXUS\" with title \"Agent NEXUS\" sound name \"Glass\"" 2>/dev/null
else
    echo "" >> "$LOG"
    echo "$(date '+%d/%m/%Y %H:%M')  ✗  ÉCHEC ($FORMAT, code $CODE, attente réseau ${ATTENTE}s) — détail" >> "$LOG"
    tail -30 "$BRUT" | sed 's/^/    /' >> "$LOG"
    osascript -e "display notification \"L'agent a échoué — voir Agent/Technique/execution.log\" with title \"Agent NEXUS\"" 2>/dev/null
fi
rm -f "$BRUT"

# le journal ne doit pas grossir indéfiniment : on garde les 200 dernières lignes
if [ "$(wc -l < "$LOG")" -gt 200 ]; then
    tail -200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

# on garde 90 jours de rapports : ils sont la mémoire de l'agent
find "$PROJECT_DIR/Agent/Rapports" -name "*.md" -mtime +90 -delete
