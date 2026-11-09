#!/bin/bash
# ═══════════════════════════════════════════════════════
#  IA Formation Radar — Mise à jour quotidienne (PythonAnywhere)
#  Configuré via Scheduled Tasks sur PythonAnywhere
# ═══════════════════════════════════════════════════════

PROJECT_DIR="/home/habertvictor12/habertvictor"
PYTHON="/usr/bin/python3.10"
LOG_FILE="$PROJECT_DIR/logs/update_$(date +%Y-%m-%d).log"

mkdir -p "$PROJECT_DIR/logs"
cd "$PROJECT_DIR"

echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"
echo "  MISE À JOUR — $(date '+%d/%m/%Y %H:%M')" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "▶ 1/8 Offres d'emploi (LinkedIn + France Travail)..." >> "$LOG_FILE"
$PYTHON manage.py scrape_jobs --limit 30 >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 2/8 Actualités & RSS..." >> "$LOG_FILE"
$PYTHON manage.py scrape_news --limit 30 >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 3/8 Communautés (Reddit, HN, SO)..." >> "$LOG_FILE"
$PYTHON manage.py scrape_communities --limit 20 >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 4/8 Tendances (GitHub, PyPI)..." >> "$LOG_FILE"
$PYTHON manage.py scrape_trends >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 5/8 Appels d'offres (BOAMP)..." >> "$LOG_FILE"
$PYTHON manage.py scrape_boamp >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 6/8 Formations existantes..." >> "$LOG_FILE"
$PYTHON manage.py scrape_formations >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 7/8 Formations CPF + RNCP..." >> "$LOG_FILE"
$PYTHON manage.py scrape_cpf --limit 200 >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "▶ 8/8 Enrichissement taille entreprise..." >> "$LOG_FILE"
$PYTHON manage.py enrich_company_size >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"
echo "  TERMINÉ — $(date '+%H:%M')" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" >> "$LOG_FILE"

# Nettoyer les logs > 30 jours
find "$PROJECT_DIR/logs" -name "update_*.log" -mtime +30 -delete
