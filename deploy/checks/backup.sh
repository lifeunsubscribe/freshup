#!/usr/bin/env bash
# Disaster recovery: back up SQLite database daily

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/freshup}"
BACKUP_KEEP_DAYS=14

check_backup() {
    local db_source
    db_source=$(docker volume inspect freshup_freshup_db --format '{{.Mountpoint}}' 2>/dev/null)/freshup.db

    # Fall back to local path if not running in Docker
    [ ! -f "$db_source" ] && db_source="$REPO_DIR/data/freshup.db"
    [ ! -f "$db_source" ] && return 0  # No database yet — nothing to back up

    mkdir -p "$BACKUP_DIR"

    # Only back up once per day
    local today
    today=$(date '+%Y-%m-%d')
    local today_backup="$BACKUP_DIR/freshup-${today}.db"

    [ -f "$today_backup" ] && return 0  # Already backed up today

    # Use SQLite's .backup for a safe copy (no corruption from active writes)
    if command -v sqlite3 &>/dev/null; then
        sqlite3 "$db_source" ".backup '$today_backup'" 2>> "$LOGFILE"
    else
        cp "$db_source" "$today_backup" 2>> "$LOGFILE"
    fi

    log "BACKUP: created $today_backup"

    # Prune old backups
    find "$BACKUP_DIR" -name "freshup-*.db" -mtime "+$BACKUP_KEEP_DAYS" -delete 2>/dev/null
    local count
    count=$(find "$BACKUP_DIR" -name "freshup-*.db" | wc -l)
    log "BACKUP: $count backups retained (keeping ${BACKUP_KEEP_DAYS} days)"
}
