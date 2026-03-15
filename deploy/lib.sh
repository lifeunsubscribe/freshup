#!/usr/bin/env bash
# Shared utilities for homelab checks

LOGFILE="/var/log/homelab.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOGFILE"; }

alert() {
    # Logs with ALERT prefix — easy to grep for things that need attention
    log "ALERT: $*"
}
