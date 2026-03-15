#!/usr/bin/env bash
set -euo pipefail

# ── Homelab health runner ──────────────────────────────────
# Runs every 5 minutes via cron. Each check is a sourced file
# in checks/. To add a new service, drop a new file there and
# source it below.
# ───────────────────────────────────────────────────────────

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCKFILE="/tmp/homelab.lock"

# Shared logging
source "$DEPLOY_DIR/lib.sh"

# Prevent overlapping runs
exec 200>"$LOCKFILE"
flock -n 200 || { log "SKIP: another homelab run is in progress"; exit 0; }

# ── Load checks ────────────────────────────────────────────

source "$DEPLOY_DIR/checks/freshup.sh"
source "$DEPLOY_DIR/checks/containers.sh"
source "$DEPLOY_DIR/checks/disk-space.sh"
source "$DEPLOY_DIR/checks/backup.sh"

# ── Run checks ─────────────────────────────────────────────
# Add new check functions here as you build out the homelab.

check_freshup
check_containers
check_disk_space
check_backup
