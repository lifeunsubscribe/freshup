# FreshUp

Privacy-first kitchen management system for multi-person households.

## Quick Start

### Local Development (Mac)

The project venv is `.venv313` (Python 3.13). Everything below assumes it.

```bash
source .venv313/bin/activate
pip install -r requirements.txt        # safe to re-run; catches drift
uvicorn src.main:app --reload
```

Then open http://localhost:8000/docs for the interactive API, or hit
http://localhost:8000/health.

Note: an activated venv in your shell is not necessarily this one. Confirm with
`python -c "import fastapi"` before assuming — if that fails, you are on the
wrong interpreter.

The frontend runs separately:

```bash
cd frontend && npm install && npm run dev
```

The API applies any pending Alembic migrations on startup and seeds local test
users (`sarah@freshup.dev` / `alex@freshup.dev`, password `FreshUp2024!`) when
`ENVIRONMENT=local`.

### Running the Full Stack Locally

You do not need the Dell to develop. `docker compose up -d` brings up the API
(:8000), MinIO (:9000, console :9001), and the frontend (:80) on your laptop.
Ollama runs on the host, not in a container — the API reaches it at
`host.docker.internal:11434`. The Dell is only needed to test real multi-device
access over the house network.

```bash
cp .env.example .env
# Edit .env with your values
docker compose up -d
```

### Server Deployment (Dell/homelab)

Same compose file, run on the server. Reachable at `homelab.local`.

### Homelab Runner (Dell/homelab)

Cron job runs every 5 minutes — auto-deploys on new commits, restarts crashed containers, monitors disk space, and backs up the database daily. Run once on the server:

```bash
./deploy/install.sh
```

Logs: `tail -f /var/log/homelab.log` | Alerts only: `grep ALERT /var/log/homelab.log`

### Health Check

```
GET http://localhost:8000/health
```

Returns `schema` and `migrations` fields alongside `status` — `migrations:
"current"` means the database is at the Alembic head.

## Testing

```bash
.venv313/bin/python -m pytest -q              # full suite, ~6 min
.venv313/bin/python -m pytest -q tests/routers # one area
.venv313/bin/python -m pytest -m integration   # hits live scraper targets; excluded by default
```

Most tests build their schema with `Base.metadata.create_all()` straight from
the models, so they are fast but never execute a migration.
`tests/test_migration_chain.py` is the exception and the safety net: it upgrades
an empty database to head through the Alembic CLI and checks the result against
the models. Run it before any PR that touches `alembic/`.

## Database Migrations

```bash
.venv313/bin/alembic heads                       # MUST be exactly one line
.venv313/bin/alembic current                     # where this database sits
.venv313/bin/alembic revision -m "describe it"   # always generate, never hand-write
.venv313/bin/alembic upgrade head
```

Two rules, both learned the hard way (see ADR Section 13):

1. **Always create migrations with `alembic revision`.** Hand-written files get
   `down_revision` wrong and branch the chain. Multiple heads make the API fail
   to start, because `_ensure_schema()` upgrades to head on every boot.
2. **Write against the database, not the model.** Before dropping a constraint,
   index, or column, confirm an earlier migration actually created it. The
   model's `__table_args__` is the intended end state, not current reality.

## Project Structure

```
freshup/
├── docker-compose.yml    # Container orchestration
├── Dockerfile            # API container build
├── requirements.txt      # Python dependencies
├── .env.example          # Environment config template
├── alembic/versions/     # Migrations — see ADR Section 13 before adding one
├── deploy/
│   ├── homelab.sh        # Main runner (cron entry point)
│   ├── install.sh        # One-time server setup
│   ├── lib.sh            # Shared logging utilities
│   └── checks/
│       ├── freshup.sh    # Git pull + smart rebuild
│       ├── containers.sh # Restart crashed containers
│       ├── disk-space.sh # Disk usage warnings
│       └── backup.sh     # Daily SQLite backup (14-day retention)
├── frontend/             # React + Vite + Tailwind
└── src/
    ├── main.py           # FastAPI entry point
    ├── config.py         # Environment-based settings
    ├── db/
    │   ├── database.py   # SQLAlchemy engine & session
    │   └── models/       # Entity models (Phase 1B)
    ├── routers/          # API route handlers (Phase 1C-1G, 2.5C-E)
    └── services/         # Business logic layer
        └── storage_service.py  # MinIO/S3 abstraction
```

## Architecture

See `docs/FreshUp-ADR.md` for full architecture decisions and rationale.
Section 0 is a current implementation status snapshot; Section 13 covers
migration discipline.

`docs/implementation-plan-recipe-engagement.md` is the detailed Phase 2.5 spec.
Delete it once 2.5F–I are done.
