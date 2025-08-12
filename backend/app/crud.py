from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import Job

def upsert_job(session: Session, provider_name: str, job: dict) -> Job:
    """
    Deduplicerar på (provider, external_id). Uppdaterar titel mm om annonsen redan finns.
    """
    stmt = select(Job).where(
        Job.provider == provider_name,
        Job.external_id == job["external_id"],
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing:
        existing.title = job.get("title", existing.title)
        existing.employer = job.get("employer", existing.employer)
        existing.city = job.get("city", existing.city)
        existing.region = job.get("region", existing.region)
        existing.url = job.get("url", existing.url)
        existing.description = job.get("description", existing.description)
        existing.published_at = job.get("published_at", existing.published_at)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    new = Job(
        provider=provider_name,
        external_id=job["external_id"],
        title=job.get("title", ""),
        employer=job.get("employer", ""),
        city=job.get("city", ""),
        region=job.get("region", ""),
        url=job.get("url", ""),
        description=job.get("description", ""),
        published_at=job.get("published_at"),
    )
    session.add(new)
    session.commit()
    session.refresh(new)
    return new
