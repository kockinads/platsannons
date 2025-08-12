from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import asyncio
import importlib

from .database import Base, engine, SessionLocal
from .crud import upsert_job
from .models import Job

# === Konfig ===
ADMIN_TOKEN = "KOCKIN2025"  # byt gärna till env-variabel senare

app = FastAPI(title="Platsannons")

# CORS – tillåt frontend på vilken domän du kör
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # snällt läge just nu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Skapa tabeller om de saknas
Base.metadata.create_all(bind=engine)

# Hjälpfunktion: ladda providers dynamiskt
def load_providers():
    module_paths = [
        "app.providers.arbetsformedlingen",
    ]
    providers = []
    for path in module_paths:
        mod = importlib.import_module(path)
        providers.append(mod)
    return providers

# Health
@app.get("/")
def health():
    return {"ok": True, "service": "platsannons"}

# Admin: trigger harvest manuellt
@app.post("/api/admin/harvest")
async def admin_harvest(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    providers = load_providers()

    async def handle_provider(provider_module):
        provider_name = getattr(provider_module, "PROVIDER_NAME",
                                provider_module.__name__.rsplit(".", 1)[-1])
        jobs: List[dict] = await provider_module.fetch({})
        with SessionLocal() as session:
            for job in jobs:
                upsert_job(session, provider_name, job)

    await asyncio.gather(*(handle_provider(p) for p in providers))
    return {"ok": True, "counts": {"arbetsformedlingen": 0}}  # count kan byggas ut senare

# (Valfritt) enkel endpoint för att lista jobb
@app.get("/api/jobs")
def list_jobs(limit: int = 50, offset: int = 0):
    with SessionLocal() as session:
        q = session.query(Job).order_by(Job.published_at.desc()).offset(offset).limit(limit)
        items = [j.to_dict() for j in q.all()]
    return {"items": items, "count": len(items)}
