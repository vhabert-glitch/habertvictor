#!/bin/bash
# Setup cron jobs for IA Formation Radar
# Usage: bash scripts/setup_cron.sh

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="python3"
MANAGE="$PROJECT_DIR/manage.py"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

echo "Configuration des tâches cron pour IA Formation Radar"
echo "Répertoire: $PROJECT_DIR"
echo ""

# Sauvegarder le crontab actuel
crontab -l > /tmp/current_cron 2>/dev/null || true

# Supprimer les anciennes entrées IA Formation Radar
grep -v "ia-formation-radar" /tmp/current_cron > /tmp/new_cron 2>/dev/null || true

# Ajouter les nouvelles tâches
cat >> /tmp/new_cron << EOF

# === IA Formation Radar — Extraction automatique ===
# Offres d'emploi : tous les jours à 6h
0 6 * * * cd $PROJECT_DIR && $PYTHON $MANAGE scrape_jobs --source all >> $LOG_DIR/jobs.log 2>&1

# Actualités RSS : tous les jours à 7h et 19h
0 7,19 * * * cd $PROJECT_DIR && $PYTHON $MANAGE scrape_news >> $LOG_DIR/news.log 2>&1

# Communautés (Reddit, HN, SO) : toutes les 6 heures
0 */6 * * * cd $PROJECT_DIR && $PYTHON $MANAGE scrape_communities --source all >> $LOG_DIR/communities.log 2>&1

# Signaux sociaux : toutes les 6 heures (décalé de 30 min)
30 */6 * * * cd $PROJECT_DIR && $PYTHON $MANAGE scrape_social >> $LOG_DIR/social.log 2>&1

# Tendances (GitHub, PyPI) : tous les jours à 8h
0 8 * * * cd $PROJECT_DIR && $PYTHON $MANAGE scrape_trends --source all >> $LOG_DIR/trends.log 2>&1

# Rapport hebdomadaire : tous les lundis à 9h
0 9 * * 1 cd $PROJECT_DIR && $PYTHON $MANAGE generate_report --days 7 >> $LOG_DIR/reports.log 2>&1

# Nettoyage des logs : 1er de chaque mois
0 0 1 * * find $LOG_DIR -name "*.log" -mtime +30 -delete
EOF

# Installer le nouveau crontab
crontab /tmp/new_cron
rm /tmp/current_cron /tmp/new_cron 2>/dev/null

echo "Tâches cron installées :"
echo ""
crontab -l | grep "ia-formation-radar" -A 1
echo ""
echo "Logs dans: $LOG_DIR/"
echo "Pour vérifier: crontab -l"
echo "Pour supprimer: crontab -e (supprimer les lignes IA Formation Radar)"
