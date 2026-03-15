#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOMELAB_SCRIPT="$SCRIPT_DIR/homelab.sh"
LOGFILE="/var/log/homelab.log"
BACKUP_DIR="/var/backups/freshup"
CRON_ENTRY="*/5 * * * * $HOMELAB_SCRIPT"

echo "Setting up homelab runner..."

# Create log file
if [ ! -f "$LOGFILE" ]; then
    sudo touch "$LOGFILE"
    sudo chown "$USER" "$LOGFILE"
    echo "  Created $LOGFILE"
fi

# Create backup directory
if [ ! -d "$BACKUP_DIR" ]; then
    sudo mkdir -p "$BACKUP_DIR"
    sudo chown "$USER" "$BACKUP_DIR"
    echo "  Created $BACKUP_DIR"
fi

# Make scripts executable
chmod +x "$HOMELAB_SCRIPT"
chmod +x "$SCRIPT_DIR"/checks/*.sh
chmod +x "$SCRIPT_DIR/lib.sh"
echo "  Made scripts executable"

# Install cron job (skip if already present)
if crontab -l 2>/dev/null | grep -qF "homelab.sh"; then
    echo "  Cron job already installed — skipping"
else
    # Remove old freshup-only cron entry if present
    crontab -l 2>/dev/null | grep -vF "deploy.sh" | crontab - 2>/dev/null || true
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "  Installed cron job: $CRON_ENTRY"
fi

echo ""
echo "Homelab runner is active! Checks run every 5 minutes."
echo ""
echo "  What it does:"
echo "    - Pulls & deploys FreshUp on new commits"
echo "    - Restarts crashed containers"
echo "    - Warns on low disk space (85%/95%)"
echo "    - Daily SQLite backups (14-day retention)"
echo ""
echo "  Logs:     tail -f $LOGFILE"
echo "  Alerts:   grep ALERT $LOGFILE"
echo "  Manual:   $HOMELAB_SCRIPT"
echo "  Disable:  crontab -e  (remove the homelab line)"
