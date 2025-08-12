from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Iterable
from sqlalchemy.orm import Session
from sqlalchemy import select
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import logging

from .models import JobPosting, Lead

log = logging.getLogger("uvicorn.error")

# --- Normalisering helpers ----------------------------------------------------

def _norm_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return " ".join(s.strip().lower().split())

def _normalize_url(url: Optional[str]) -> str:
    """
    Normalisera URL så att olika spårningsparametrar inte skapar 'olika' länkar.
    - tar bort query-parametrar som ofta bara är tracking (utm_*, gclid, fbclid, promotion, ref)
    - behåller schema, host, path och ev. 'viktiga' query-parametrar om vi tycker det senare
    """
    if not url:
        return ""
    try:
        u = urlparse(url.strip())
        # Tillåt *inga* trackingparametrar (konservativt):
        allowed: set[str] = set()
        cleaned_query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k in allowed]
        new = u._replace(query=urlencode(cleaned_query, doseq=True), fragment="")
        # lowercasa host, normalisera path med trailing slash bort
        netloc = (new.netloc or "").lower()
        path = new.path or ""
        if path.endswith("/") and path != "/":
            path = path[:-1]
        new = new._replace(netloc=netloc, path=path)
        # slå ihop igen
        return urlunparse(new)
    except Exception:
        return url.strip()

# --- Job upsert med dubblett-koll --------------------------------------------

def upsert_job(db: Session, source: str, job: Dict[str, Any]) -> Optional[JobPosting]:
    """
    Sparar jobb. Logik:
      1) Finns (source, external_id)? -> uppdatera.
      2) Annars: leta 'möjlig dubblett' senaste 90 dagar med samma (title_norm, employer_norm, city_norm).
         - om URL finns: samma normaliserade URL → uppdatera den posten
         - annars: om publiceringsdatum ligger inom ±3 dagar, betrakta som samma post → uppdatera
      3) Om ingen träff → skapa ny.
    """
    now = datetime.utcnow()

    # Plocka ur inkommande
    title = job.get("title") or ""
    employer = job.get("employer") or ""
    city = job.get("city") or ""
    region = job.get("region") or ""
    published_at = job.get("published_at") or now
    description = job.get("description") or ""
    url = job.get("url") or ""
    external_id = str(job.get("external_id") or "")

    title_norm = _norm_text(title)
    employer_norm = _norm_text(employer)
    city_norm = _norm_text(city)
    url_norm = _normalize_url(url)

    # 1) Rakt upsert på (source, external_id) om external_id finns
    if external_id:
        existing = db.execute(
            select(JobPosting).where(
                JobPosting.source == source,
                JobPosting.external_id == external_id,
            )
        ).scalar_one_or_none()
        if existing:
            existing.title = title
            existing.employer = employer
            existing.city = city
            existing.region = region
            existing.published_at = published_at
            existing.description = description
            existing.url = url
            existing.title_norm = title_norm
            existing.employer_norm = employer_norm
            existing.city_norm = city_norm
            try:
                db.commit()
                return existing
            except Exception as e:
                db.rollback()
                log.error(f"DB commit failed for job '{title}' ({employer}, {city}) : {e}")
                return None

    # 2) Leta möjlig dubblett
    window_days = 90
    date_match_delta = timedelta(days=3)
    recent_candidates: Iterable[JobPosting] = db.execute(
        select(JobPosting).where(
            JobPosting.title_norm == title_norm,
            JobPosting.employer_norm == employer_norm,
            JobPosting.city_norm == city_norm,
            JobPosting.published_at >= now - timedelta(days=window_days),
        )
    ).scalars().all()

    chosen: Optional[JobPosting] = None
    if url_norm:
        # URL-baserad match
        for cand in recent_candidates:
            if _normalize_url(cand.url) == url_norm:
                chosen = cand
                break

    if chosen is None:
        # Datumbaserad 'nära nog' match om URL saknas/varierar
        for cand in recent_candidates:
            if abs((cand.published_at or now) - published_at) <= date_match_delta:
                chosen = cand
                break

    if chosen:
        # Uppdatera befintlig
        chosen.title = title
        chosen.employer = employer
        chosen.city = city
        chosen.region = region
        # Välj det tidigaste publiceringsdatumet (så listor inte hoppar)
        try:
            if chosen.published_at and published_at:
                chosen.published_at = min(chosen.published_at, published_at)
            else:
                chosen.published_at = published_at or chosen.published_at
        except Exception:
            chosen.published_at = published_at or chosen.published_at
        chosen.description = description
        chosen.url = url
        chosen.title_norm = title_norm
        chosen.employer_norm = employer_norm
        chosen.city_norm = city_norm
        try:
            db.commit()
            return chosen
        except Exception as e:
            db.rollback()
            log.error(f"DB commit failed for job '{title}' ({employer}, {city}) : {e}")
            return None

    # 3) Skapa ny
    obj = JobPosting(
        source=source,
        external_id=external_id or None,
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
        created_at=now,
    )
    db.add(obj)
    try:
        db.commit()
        db.refresh(obj)
        return obj
    except Exception as e:
        db.rollback()
        log.error(f"DB commit failed for job '{title}' ({employer}, {city}) : {e}")
        return None


# --- Leads (oförändrat) ------------------------------------------------------

def create_or_update_lead(db: Session, job_id: int, tier: str, notes: str | None) -> Lead:
    lead = db.execute(select(Lead).where(Lead.job_id == job_id)).scalar_one_or_none()
    now = datetime.utcnow()
    if lead:
        lead.tier = tier
        lead.notes = notes
        lead.updated_at = now
    else:
        lead = Lead(job_id=job_id, tier=tier, notes=notes, created_at=now, updated_at=now)
        db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
