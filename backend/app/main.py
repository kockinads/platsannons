# File: backend/app/main.py
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal, engine, Base, init_db
from .models import Job, Lead
from .schemas import JobOut, LeadCreate, LeadOut
from .crud import upsert_job
from .settings import settings
from .providers.arbetsformedlingen import AFProvider


app = FastAPI(title="Platsannons API")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # justera vid behov
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DB session dependency ---
async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

# --- Startup: skapa tabeller & initiera DB ---
@app.on_event("startup")
async def on_startup():
    # Skapa tabeller (SQLAlchemy 2.x + AsyncEngine korrekt sätt)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_db()
    print("Startup complete: DB ready")

# --- Healthcheck ---
@app.get("/api/health")
async def health():
    return {"ok": True}

# --- Jobs ------------------------------------------------------------------
@app.get("/api/jobs", response_model=list[JobOut])
async def list_jobs(
    hide_recruiters: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    # Just nu ignorerar vi hide_recruiters i servern; frontend kan filtrera själv.
    res = await session.execute(
        select(Job).order_by(Job.published_at.desc()).limit(500)
    )
    jobs = list(res.scalars())
    return jobs

# --- Leads -----------------------------------------------------------------
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

# --- Admin: Harvest --------------------------------------------------------
def require_admin(auth: Optional[str]) -> None:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.split(" ", 1)[1]
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid token")

@app.post("/api/admin/harvest")
async def admin_harvest(Authorization: str | None = Header(default=None)):
    require_admin(Authorization)

    provider = AFProvider()

    # Tillåt både sync och async fetch() (beroende på hur klassen är implementerad)
    maybe_coro = provider.fetch()
    jobs = await maybe_coro if asyncio.iscoroutine(maybe_coro) else maybe_coro

    saved = 0
    async with SessionLocal() as session:
        for job in jobs:
            await upsert_job(session, job)
            saved += 1
        await session.commit()

    # Använd strängnyckel så vi inte är beroende av provider.name-attribut
    return {"ok": True, "counts": {"arbetsformedlingen": saved}}

# --- Static frontend --------------------------------------------------------
# Servera Vite-bygget från ./static (kopieras dit i Dockerfile)
# Lägg denna mount SIST så att /api/*-rutter matchas först.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
