import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import SessionLocal, get_session, engine
from . import models
from .providers import arbetsformedlingen
from .crud import upsert_job

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS-inställningar (tillåt alla för enkelhet)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

providers = [arbetsformedlingen]

async def handle_provider(provider):
    """Kör en provider och sparar nya jobb i databasen."""
    jobs = await provider.fetch()
    session = next(get_session())  # Fixa generator -> session
    try:
        for job in jobs:
            upsert_job(session, job)
        session.commit()
    finally:
        session.close()

async def run_harvest():
    """Hämtar alla annonser från alla providers."""
    await asyncio.gather(*(handle_provider(p) for p in providers))

@app.on_event("startup")
async def startup_event():
    """Kör harvest vid startup."""
    await run_harvest()

@app.get("/ping")
async def ping():
    return {"status": "ok"}

@app.post("/api/admin/harvest")
async def manual_harvest():
    """Manuellt trigga harvest via API."""
    await run_harvest()
    return {"ok": True}
