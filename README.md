# FreshUp

Privacy-first kitchen management system for multi-person households.

## Quick Start

### Local Development (Mac)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

### Server Deployment (Dell/homelab)

```bash
cp .env.example .env
# Edit .env with your values
docker compose up -d
```

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

## Project Structure

```
freshup/
├── docker-compose.yml    # Container orchestration
├── Dockerfile            # API container build
├── requirements.txt      # Python dependencies
├── .env.example          # Environment config template
├── deploy/
│   ├── homelab.sh        # Main runner (cron entry point)
│   ├── install.sh        # One-time server setup
│   ├── lib.sh            # Shared logging utilities
│   └── checks/
│       ├── freshup.sh    # Git pull + smart rebuild
│       ├── containers.sh # Restart crashed containers
│       ├── disk-space.sh # Disk usage warnings
│       └── backup.sh     # Daily SQLite backup (14-day retention)
└── src/
    ├── main.py           # FastAPI entry point
    ├── config.py         # Environment-based settings
    ├── db/
    │   ├── database.py   # SQLAlchemy engine & session
    │   └── models/       # Entity models (Phase 1B)
    ├── routers/          # API route handlers (Phase 1C-1G)
    └── services/         # Business logic layer
        └── storage_service.py  # MinIO/S3 abstraction
```

## Architecture

See `docs/FreshUp-ADR.md` for full architecture decisions and rationale.
