#!/usr/bin/env bash
# Test gate for sharkrite worktrees: backend (pytest) and frontend (vitest).
#
# Why this exists: the gate's auto-detection looks for a root package.json or
# Makefile. FreshUp has neither (package.json lives in frontend/), so it fell
# back to pytest alone and every frontend change merged with its tests unrun.
# Referenced from .rite/config as RITE_TEST_COMMAND.
#
# Worktrees have no .venv and no frontend/node_modules of their own; both are
# borrowed from the main checkout, found through `git worktree list`.
set -u

root=$(cd "$(dirname "$0")/.." && pwd)
main=$(git -C "$root" worktree list --porcelain | sed -n 's/^worktree //p' | head -1)
main=${main:-$root}

status=0

# --- backend -----------------------------------------------------------------
py="$root/.venv/bin/python"
[ -x "$py" ] || py="$main/.venv/bin/python"
if [ -x "$py" ]; then
  echo "[rite-test] backend: $py -m pytest"
  (cd "$root" && "$py" -m pytest -q -p no:cacheprovider) || status=1
else
  echo "[rite-test] backend: no .venv found in $root or $main" >&2
  status=1
fi

# --- frontend ----------------------------------------------------------------
fe="$root/frontend"
if [ -f "$fe/package.json" ]; then
  if [ ! -e "$fe/node_modules" ]; then
    if [ -d "$main/frontend/node_modules" ]; then
      ln -s "$main/frontend/node_modules" "$fe/node_modules"
      echo "[rite-test] frontend: linked node_modules from $main"
    else
      echo "[rite-test] frontend: no node_modules in $fe or $main/frontend; run npm ci there" >&2
      exit 1
    fi
  fi
  echo "[rite-test] frontend: tsc (build config) + vitest run"
  (cd "$fe" && npx tsc --project tsconfig.build.json) || status=1
  (cd "$fe" && npx vitest run) || status=1
fi

exit $status
