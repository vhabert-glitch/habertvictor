#!/bin/bash
# ═══════════════════════════════════════════════════════
#  IA Formation Radar — Mise à jour quotidienne automatique
#  8 sources de données + CPF/RNCP + enrichissement taille
#  Exécuté tous les jours à 6h via launchd
# ═══════════════════════════════════════════════════════

PROJECT_DIR="/Users/habertvictor/ia-formation-radar"
PYTHON="/usr/bin/python3"
LOG_FILE="$PROJECT_DIR/logs/update_$(date +%Y-%m-%d).log"

mkdir -p "$PROJECT_DIR/logs"

# Attendre que le réseau soit prêt
ATTENTE=0
until curl -s --max-time 5 -o /dev/null https://pypi.org; do
    [ $ATTENTE -ge 600 ] && break
    sleep 20
    ATTENTE=$((ATTENTE + 20))
done

cd "$PROJECT_DIR"

echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"
echo "  MISE À JOUR — $(date '+%d/%m/%Y %H:%M')" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "▶ 1/9 Offres d'emploi..." >> "$LOG_FILE"
$PYTHON manage.py scrape_jobs --limit 30 >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 2/9 Actualités & RSS..." >> "$LOG_FILE"
$PYTHON manage.py scrape_news --limit 30 >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 3/9 Communautés (Reddit, HN, SO)..." >> "$LOG_FILE"
$PYTHON manage.py scrape_communities --limit 20 >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 4/9 Tendances (GitHub, PyPI)..." >> "$LOG_FILE"
$PYTHON manage.py scrape_trends >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 5/9 Appels d'offres (BOAMP)..." >> "$LOG_FILE"
$PYTHON manage.py scrape_boamp >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 6/9 Formations existantes..." >> "$LOG_FILE"
$PYTHON manage.py scrape_formations >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 7/9 Formations CPF + RNCP..." >> "$LOG_FILE"
$PYTHON manage.py scrape_cpf --limit 200 >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 8/9 Enrichissement taille entreprise..." >> "$LOG_FILE"
$PYTHON manage.py enrich_company_size >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 9/9 Sync vers PythonAnywhere..." >> "$LOG_FILE"
cd "$PROJECT_DIR" && git add -A && git commit -m "data: update $(date +%Y-%m-%d)" 2>/dev/null
git push origin main >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"
echo "  TERMINÉ — $(date '+%H:%M')" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"

# Nettoyer les logs > 30 jours
find "$PROJECT_DIR/logs" -name "update_*.log" -mtime +30 -delete
