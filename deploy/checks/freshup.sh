#!/usr/bin/env bash
# FreshUp: poll GitHub and deploy on changes

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

check_freshup() {
    cd "$REPO_DIR"

    git fetch origin main 2>/dev/null

    local LOCAL REMOTE
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main)

    # Nothing new — stay silent
    [ "$LOCAL" = "$REMOTE" ] && return 0

    log "FRESHUP UPDATE: ${LOCAL:0:7} -> ${REMOTE:0:7}"
    git pull origin main >> "$LOGFILE" 2>&1
    if [ $? -ne 0 ]; then
        alert "Git pull failed — check $LOGFILE"
        return 1
    fi

    local CHANGED
    CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE")

    local NEEDS_BUILD=false
    local NEEDS_RESTART=false
    local NEEDS_FRONTEND_RESTART=false

    echo "$CHANGED" | grep -qE '^(Dockerfile|requirements\.txt|docker-compose\.yml)' && NEEDS_BUILD=true
    echo "$CHANGED" | grep -qE '^src/' && NEEDS_RESTART=true
    echo "$CHANGED" | grep -qE '^frontend/' && NEEDS_FRONTEND_RESTART=true

    if [ "$NEEDS_BUILD" = true ]; then
        log "FRESHUP REBUILD: infrastructure files changed"
        docker compose -f "$REPO_DIR/docker-compose.yml" up -d --build >> "$LOGFILE" 2>&1
        if [ $? -ne 0 ]; then
            alert "Docker rebuild failed — check $LOGFILE"
            return 1
        fi
    else
        if [ "$NEEDS_RESTART" = true ]; then
            log "FRESHUP RESTART: source files changed"
            docker compose -f "$REPO_DIR/docker-compose.yml" restart api >> "$LOGFILE" 2>&1
            if [ $? -ne 0 ]; then
                alert "API restart failed — check $LOGFILE"
                return 1
            fi
        fi
        if [ "$NEEDS_FRONTEND_RESTART" = true ]; then
            log "FRESHUP RESTART FRONTEND: frontend files changed"
            docker compose -f "$REPO_DIR/docker-compose.yml" restart frontend >> "$LOGFILE" 2>&1
            if [ $? -ne 0 ]; then
                alert "Frontend restart failed — check $LOGFILE"
                return 1
            fi
        fi
        if [ "$NEEDS_RESTART" = false ] && [ "$NEEDS_FRONTEND_RESTART" = false ]; then
            log "FRESHUP PULL ONLY: no deploy-relevant files changed"
        fi
    fi

    log "FRESHUP DONE: now at $(git rev-parse --short HEAD)"
    return 0
}
