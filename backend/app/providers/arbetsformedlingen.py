# backend/app/providers/arbetsformedlingen.py
from __future__ import annotations
import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List
from ..settings import settings
from .base import ROLE_KEYWORDS  # använder kartläggningen i base.py
import logging

log = logging.getLogger("uvicorn.error")

# Gör en bred sökfråga – utan extra titel­filter
ALL_KEYWORDS: List[str] = sorted({kw.lower() for kws in ROLE_KEYWORDS.values() for kw in kws})
ROLE_QUERY = " OR ".join(ALL_KEYWORDS)

def _flatten_description(hit: Dict[str, Any]) -> str:
    desc = hit.get("description")
    if isinstance(desc, dict):
        parts: List[str] = []
        for key in ("text", "company_information", "needs", "requirements", "conditions"):
            val = desc.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
        return "\n\n".join(parts)
    if isinstance(desc, str):
        return desc
    return ""

def _parse_published(v: str | None) -> datetime:
    if not v:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()

class AFProvider:
    name = "arbetsformedlingen"

    async def fetch(self) -> List[Dict[str, Any]]:
        params = {
            "q": ROLE_QUERY,
            "limit": 100,
        }
        headers = {
            "User-Agent": settings.af_user_agent,
            "Accept": "application/json",
            "Accept-Language": "sv-SE",
        }
        if settings.jobtech_api_key:
            headers["api-key"] = settings.jobtech_api_key

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.get(settings.af_base_url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            log.exception(f"AF request failed: {e}")
            return []

        hits = data.get("hits") or []
        log.info(f"HARVEST: AF returned {len(hits)} hits for q='{params['q']}'")

        jobs: List[Dict[str, Any]] = []
        for hit in hits:
            title = (hit.get("headline") or "").strip()

            employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
            wp = (hit.get("workplace_addresses") or [{}])[0] or {}
            city = (wp.get("municipality") or "").strip()
            region = (wp.get("region") or "").strip()
            url = (hit.get("application_details") or {}).get("url") or hit.get("webpage_url") or ""

            jobs.append({
                "source": self.name,
                "external_id": str(hit.get("id") or ""),
                "title": title if title else "Annons",
                "employer": employer,
                "city": city,
                "region": region,
                "published_at": _parse_published(hit.get("publication_date")),
                "description": _flatten_description(hit),
                "url": url,
            })
        return jobs
