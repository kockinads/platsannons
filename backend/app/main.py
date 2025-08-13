# backend/app/main.py
from __future__ import annotations
import asyncio
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import SessionLocal, engine, Base, init_db
from .models import Job, Lead
from .schemas import JobOut, LeadCreate, LeadOut
from .crud import upsert_job
from .providers.arbetsformedlingen import AFProvider
from .settings import settings

app = FastAPI(title="Platsannons API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

@app.on_event("startup")
async def on_startup():
    # Skapa tabeller med AsyncEngine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_db()

@app.get("/api/health")
async def health():
    return {"ok": True}

# --- Jobs ------------------------------------------------------------------
@app.get("/api/jobs", response_model=list[JobOut])
async def list_jobs(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Job).order_by(Job.published_at.desc()).limit(200))
    return list(res.scalars())

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
def require_admin(auth: str | None) -> None:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.split(" ", 1)[1]
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid token")

@app.post("/api/admin/harvest")
async def admin_harvest(Authorization: str | None = Header(default=None)):
    require_admin(Authorization)
    provider = AFProvider()

    async with SessionLocal() as session:
        jobs = await provider.fetch()
        saved = 0
        for job in jobs:
            await upsert_job(session, job)
            saved += 1
        await session.commit()
    return {"ok": True, "counts": {provider.name: saved}}
