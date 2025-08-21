# backend/app/crud.py
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Job

async def upsert_job(session: AsyncSession, job: dict) -> Job:
    """
    Skapar eller uppdaterar ett Job baserat på (source, external_id).
    Returnerar Job-objektet. Kräver en aktiv AsyncSession.
    """
    q = select(Job).where(
        Job.source == job["source"],
        Job.external_id == job["external_id"],
    )
    res = await session.execute(q)
    existing = res.scalar_one_or_none()

    if existing:
        existing.title = job.get("title", existing.title)
        existing.employer = job.get("employer", existing.employer)
        existing.city = job.get("city", existing.city)
        existing.region = job.get("region", existing.region)
        existing.published_at = job.get("published_at", existing.published_at)
        existing.description = job.get("description", existing.description)
        existing.url = job.get("url", existing.url)
        existing.updated_at = datetime.utcnow()
        await session.flush()
        return existing

    obj = Job(
        source=job["source"],
        external_id=job["external_id"],
        title=job.get("title", ""),
        employer=job.get("employer", "Okänd arbetsgivare"),
        city=job.get("city", ""),
        region=job.get("region", ""),
        published_at=job.get("published_at"),
        description=job.get("description", ""),
        url=job.get("url", ""),
    )
    session.add(obj)
    await session.flush()
    return obj
