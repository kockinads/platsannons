from sqlalchemy.orm import Session
from sqlalchemy import select
from . import models
from datetime import datetime
import re

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def upsert_job(db: Session, source: str, job: dict) -> models.JobPosting | None:
    title_norm = _norm(job.get("title"))
    employer_norm = _norm(job.get("employer"))
    city_norm = _norm(job.get("city"))
    published_at = job.get("published_at")

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
        external_id=str(job.get("external_id")),
        title=job.get("title"),
        employer=job.get("employer"),
        city=job.get("city"),
        region=job.get("region", ""),
        published_at=published_at,
        description=job.get("description", ""),
        url=job.get("url", ""),
        title_norm=title_norm,
        employer_norm=employer_norm,
        city_norm=city_norm,
    )
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        return None
    db.refresh(item)
    return item

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
