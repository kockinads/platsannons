# backend/app/main.py
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal, engine, Base, init_db
from .models import Job, Lead
from .schemas import JobOut, LeadCreate, LeadOut
from .crud import upsert_job
from .providers.arbetsformedlingen import AFProvider
from .settings import settings


app = FastAPI(title="Platsannons API")

# CORS – öppet för frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # just nu öppet, kan snävas in
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency: DB-session
async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


# Startup: skapa tabeller och testa DB
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_db()
    print("Startup complete: DB ready")


@app.get("/api/health")
async def health():
    return {"ok": True}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
@app.get("/api/jobs", response_model=list[JobOut])
async def list_jobs(
    hide_recruiters: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    # Grundquery
    q = select(Job).order_by(Job.published_at.desc()).limit(500)

    # (Valfritt) filtrera bort uppenbara bemannings-/rekryteringsannonser
    # (enkel heuristik – förbättra vid behov)
    if hide_recruiters:
        # Låt det vara en enkel fetch och filtrera i Python (billigt för <=500)
        res = await session.execute(q)
        jobs = list(res.scalars())

        def is_recruiter(name: str) -> bool:
            n = (name or "").lower()
            return any(
                bad in n
                for bad in [
                    "bemanning",
                    "rekrytering",
                    "rekryterings",
                    "headhunt",
                    "staffing",
                    "kompetenspartner",
                ]
            )

        jobs = [j for j in jobs if not is_recruiter(j.employer)]
        return jobs

    res = await session.execute(q)
    return list(res.scalars())


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------
@app.post("/api/leads", response_model=LeadOut)
async def create_lead(payload: LeadCreate, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    obj = Lead(job_id=payload.job_id, tier=payload.tier, notes=payload.notes)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# Admin: Harvest
# ---------------------------------------------------------------------------
def require_admin(auth_header: Optional[str]) -> None:
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth_header.split(" ", 1)[1]
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid token")


@app.post("/api/admin/harvest")
async def admin_harvest(Authorization: str | None = Header(default=None)):
    require_admin(Authorization)
    provider = AFProvider()

    # Hämta jobb – stöder både sync och async fetch()
    maybe_coroutine = provider.fetch()
    jobs = await maybe_coroutine if asyncio.iscoroutine(maybe_coroutine) else maybe_coroutine

    saved = 0
    async with SessionLocal() as session:
        for job in jobs:
            await upsert_job(session, job)
            saved += 1
        await session.commit()

    return {"ok": True, "counts": {provider.name: saved}}


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
# Servera Vite-builden (frontend) som ligger i /static
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


@app.get("/")
async def serve_index():
    # Leverera index.html (som i sin tur laddar /assets/*)
    return FileResponse("static/index.html")
