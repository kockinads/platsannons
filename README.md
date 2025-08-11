# Platsannons-aggregator (kök/matsal/bar/lokalvård)

Single-URL deploy: backend (FastAPI) **serverar även frontend**. Du får **en** publik adress att dela.

## Kör lokalt (Docker)
```bash
docker compose up --build
```
Appen nås på **http://localhost:8000** (både webb och API).

## Miljövariabler (backend)
- `DATABASE_URL`
- `AF_BASE_URL` (default: https://jobsearch.api.jobtechdev.se)
- `AF_USER_AGENT`
- `RECRUITER_KEYWORDS`
- `ACCESS_TOKEN` (delad åtkomstkod för enkel login)

## Deploy till Render (en tjänst)
1. Skapa Managed PostgreSQL i Render, kopiera **Internal Database URL**.
2. New → Web Service → koppla GitHub → Environment: **Docker** (använder repo-rotens `Dockerfile`).
3. Sätt env vars: `DATABASE_URL`, `ACCESS_TOKEN`, `AF_*`, `RECRUITER_KEYWORDS`.
4. Öppna den publika URL:en → **Logga in** med din åtkomstkod.
