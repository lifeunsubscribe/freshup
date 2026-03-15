#!/usr/bin/env bash
# Disk space: warn when usage gets high, prune stale Docker images

DISK_WARN_PERCENT=85
DISK_CRITICAL_PERCENT=95

check_disk_space() {
    # Check all real filesystems (skip tmpfs, devtmpfs, etc.)
    while read -r usage mount; do
        local pct="${usage%\%}"

        if [ "$pct" -ge "$DISK_CRITICAL_PERCENT" ]; then
            alert "DISK CRITICAL: $mount is at ${usage} — free space immediately"
        elif [ "$pct" -ge "$DISK_WARN_PERCENT" ]; then
            alert "DISK WARNING: $mount is at ${usage}"
        fi
    done < <(df -h --output=pcent,target -x tmpfs -x devtmpfs -x squashfs 2>/dev/null | tail -n +2)

    # Prune dangling Docker images (stale layers from rebuilds)
    local pruned
    pruned=$(docker image prune -f 2>/dev/null | tail -1)
    if [[ "$pruned" != *"0B"* ]] && [[ -n "$pruned" ]]; then
        log "DOCKER PRUNE: $pruned"
    fi
}
