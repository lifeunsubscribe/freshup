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
