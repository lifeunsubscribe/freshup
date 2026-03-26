#!/usr/bin/env bash
# Container health: verify expected containers are running, restart if crashed

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Add container names here as you add services
EXPECTED_CONTAINERS=(
    "freshup-api"
    "freshup-minio"
    "freshup-frontend"
)

check_containers() {
    local running
    running=$(docker ps --format '{{.Names}}' 2>/dev/null)

    for container in "${EXPECTED_CONTAINERS[@]}"; do
        if echo "$running" | grep -q "^${container}$"; then
            continue
        fi

        # Container exists but stopped — restart it
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            alert "Container $container is stopped — restarting"
            docker start "$container" >> "$LOGFILE" 2>&1
            if [ $? -ne 0 ]; then
                alert "Failed to start $container — check $LOGFILE"
            fi
        else
            # Container doesn't exist at all — bring up the whole stack
            alert "Container $container not found — bringing up stack"
            docker compose -f "$REPO_DIR/docker-compose.yml" up -d >> "$LOGFILE" 2>&1
            if [ $? -ne 0 ]; then
                alert "Failed to bring up stack — check $LOGFILE"
            fi
            return  # up -d handles all containers, no need to continue the loop
        fi
    done
}
