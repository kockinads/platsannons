from sqlalchemy.orm import Session
from sqlalchemy import select
from . import models
from datetime import datetime
import logging
import re

logger = logging.getLogger("uvicorn.error")

# Maxlängder enligt models.py
MAX_TITLE = 300
MAX_EMPLOYER = 300
MAX_CITY = 200
MAX_URL = 1000  # kolumnen är String(1000)

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _clip(s: str | None, n: int) -> str:
    if not s:
        return ""
    s = s.strip()
    return s if len(s) <= n else s[: n - 1]

# --- Jobb ---

def upsert_job(db: Session, source: str, job: dict) -> models.JobPosting | None:
    # Sanitera & trunkera innan vi jämför/sparar
    title = _clip(job.get("title") or "", MAX_TITLE)
    employer = _clip(job.get("employer") or "", MAX_EMPLOYER)
    city = _clip(job.get("city") or "", MAX_CITY)
    region = _clip(job.get("region") or "", MAX_CITY)  # region-kolumnen är 200 i modellen
    url = _clip(job.get("url") or "", MAX_URL)
    description = job.get("description") or ""

    published_at = job.get("published_at")
    if not isinstance(published_at, datetime):
        published_at = datetime.utcnow()

    title_norm = _norm(title)
    employer_norm = _norm(employer)
    city_norm = _norm(city)

    # Dedup: samma titel+arbetsgivare+stad+datum
    stmt = select(models.JobPosting).where(
        models.JobPosting.title_norm == title_norm,
        models.JobPosting.employer_norm == employer_norm,
        models.JobPosting.city_norm == city_norm,
        models.JobPosting.published_at == published_at,
    )
    existing = db.execute(stmt).scalars().first()
    if existing:
        return existing

    item = models.JobPosting(
        source=source,
        external_id=str(job.get("external_id") or ""),
        title=title,
        employer=employer,
        city=city,
        region=region,
        published_at=published_at,
        description=description,
        url=url,
        title_norm=title_norm,
        employer_norm=employer_norm,
        city_norm=city_norm,
    )
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
        return item
    except Exception as e:
        db.rollback()
        logger.exception(f"DB commit failed for job '{title}' ({employer}, {city}) : {e}")
        return None

# --- Leads ---

def create_or_update_lead(db: Session, job_id: int, tier: str | None, notes: str | None) -> models.Lead:
    stmt = select(models.Lead).where(models.Lead.job_id == job_id)
    lead = db.execute(stmt).scalars().first()
    if lead:
        if tier:
            lead.tier = tier
        if notes is not None:
            lead.notes = notes
        lead.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(lead)
        return lead
    lead = models.Lead(job_id=job_id, tier=tier or "U", notes=notes or "")
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
