from fastapi import FastAPI, Depends, Query, Response, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
import csv
import io
import asyncio
import os
import re
import logging

from .database import get_session, engine, SessionLocal
from .models import Base, JobPosting, Lead
from .schemas import JobBase, LeadIn, LeadOut
from .crud import upsert_job, create_or_update_lead
from .settings import settings
from .providers.arbetsformedlingen import AFProvider
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Platsannons-aggregator")

# CORS (backend serverar även frontend, men låt vara öppet vid test)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Skapa DB-tabeller
Base.metadata.create_all(bind=engine)

# Datakällor (lägg fler senare)
providers = [AFProvider()]

# --------- Hjälp: filtrera bort rekryteringsföretag ---------
recruiter_re = re.compile(
    r"|".join(map(re.escape, settings.recruiter_keywords)), re.I
) if settings.recruiter_keywords else None

def is_recruiter(name: str, description: str) -> bool:
    if not recruiter_re:
        return False
    text = f"{name or ''} {description or ''}"
    return bool(recruiter_re.search(text))

# --------- Enkel auth: delad åtkomstkod i Authorization: Bearer <kod> ---------
async def require_auth(authorization: str | None = Header(default=None)):
    # Om ACCESS_TOKEN är tomt är auth avstängd
    if not settings.access_token:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")
    token = authorization.split(" ", 1)[1]
    if token != settings.access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# --------- Insamling (scheduler + manuell trigger) ---------
scheduler = AsyncIOScheduler()

async def run_harvest():
    """
    Kör alla providers, spara jobb till DB och logga hur många som sparades.
    Returnerar en dict {provider_namn: antal}.
    """
    counts: dict[str, int | str] = {}

    async def handle_provider(p):
        n = 0
        try:
            async for job in p.fetch({}):
                with SessionLocal() as db:
                    saved = upsert_job(db, p.name, job)
                    if saved:
                        n += 1
            counts[p.name] = n
            logger.info(f"HARVEST: {p.name} saved {n} jobs")
        except Exception as e:
            counts[p.name] = f"error: {e!r}"
            logger.exception(f"Provider {p.name} failed: {e}")

    await asyncio.gather(*(handle_provider(p) for p in providers))
    return counts

@app.on_event("startup")
async def startup_event():
    # Försök hämta direkt vid start men låt appen starta även om något felar
    try:
        await run_harvest()
    except Exception as e:
        logger.exception(f"Harvest on startup failed: {e}")
    # Schemalägg daglig körning 03:00
    scheduler.add_job(run_harvest, "cron", hour=3, minute=0)
    scheduler.start()

# Admin-trigger för att köra insamling NU (GET och POST). Kräver inloggning.
@app.get("/api/admin/harvest", dependencies=[Depends(require_auth)])
@app.post("/api/admin/harvest", dependencies=[Depends(require_auth)])
async def trigger_harvest():
    counts = await run_harvest()
    return {"ok": True, "counts": counts}

# --------- Health ---------
@app.get("/api/health")
async def health():
    return {"ok": True}

# --------- API: Jobb ---------
@app.get("/api/jobs", response_model=List[JobBase], dependencies=[Depends(require_auth)])
async def list_jobs(
    roles: List[str] = Query(default=[]),
    region: str | None = None,
    city: str | None = None,
    hide_recruiters: bool = False,
    db: Session = Depends(get_session),
):
    stmt = select(JobPosting).order_by(JobPosting.published_at.desc())
    if region:
        stmt = stmt.where(JobPosting.region.ilike(f"%{region}%"))
    if city:
        stmt = stmt.where(JobPosting.city.ilike(f"%{city}%"))
    for r in roles:
        stmt = stmt.where(JobPosting.title.ilike(f"%{r}%"))

    rows = db.execute(stmt).scalars().all()
    if hide_recruiters:
        rows = [r for r in rows if not is_recruiter(r.employer, r.description)]
    return rows

# --------- API: Leads ---------
@app.post("/api/leads", response_model=LeadOut, dependencies=[Depends(require_auth)])
async def save_lead(payload: LeadIn, db: Session = Depends(get_session)):
    lead = create_or_update_lead(db, payload.job_id, payload.tier, payload.notes)
    return lead

@app.get("/api/leads", response_model=List[LeadOut], dependencies=[Depends(require_auth)])
async def list_leads(tier: str | None = None, db: Session = Depends(get_session)):
    stmt = select(Lead).order_by(Lead.updated_at.desc())
    if tier in {"A", "B", "C", "U"}:
        stmt = stmt.where(Lead.tier == tier)
    rows = db.execute(stmt).scalars().all()
    return rows

@app.get("/api/leads/export", dependencies=[Depends(require_auth)])
async def export_leads(db: Session = Depends(get_session)):
    stmt = select(Lead, JobPosting).join(JobPosting, Lead.job_id == JobPosting.id)
    rows = db.execute(stmt).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["tier", "notes", "title", "employer", "city", "region", "published_at", "url"])
    for lead, job in rows:
        writer.writerow([
            lead.tier, lead.notes, job.title, job.employer,
            job.city, job.region, job.published_at.isoformat(), job.url
        ])
    csv_data = buf.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"}
    )

# --------- Static frontend (Vite build) ---------
# Dockerfile kopierar /fe/dist till /app/static
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
if os.path.isdir(static_dir):
    # /assets (JS/CSS) mappas direkt
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

# SPA-fallback: alla okända rutter -> index.html
@app.get("/{full_path:path}")
async def spa(full_path: str):
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend är inte byggd"}
