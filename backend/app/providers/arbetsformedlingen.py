# File: backend/app/providers/arbetsformedlingen.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from ..settings import settings

log = logging.getLogger("uvicorn.error")

# Blockera titlar som innehåller "chef" (t.ex. kökschef, restaurangchef, barchef)
TITLE_BLOCK = ["chef"]

# Sökord – undvik kolon och andra tecken som kan ge 400 på Jobtech API.
# (t.ex. "1:e kock" tas bort)
KEYWORDS = [
    "kock", "kockar", "restaurangkock",
    "köksbiträde", "köksmästare", "souschef",
    "kallskänk", "kallskänka",
    "kökspersonal", "matlagning",
    "restaurangkök", "varmkök", "kallkök",
    "pizzabagare", "pizzabakare",
    "servitör", "servitris", "serveringspersonal",
    "hovmästare",
    "bartender", "barpersonal",
    "sommelier",
    # Vi skippar "restaurangchef", "barchef", "kökschef" osv pga TITLE_BLOCK ändå
]

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
        # Gör UTC-naiv datetime
        return (
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
    except Exception:
        return datetime.utcnow()

class AFProvider:
    name = "arbetsformedlingen"

    def __init__(self) -> None:
        self.base_url = settings.af_base_url or "https://jobsearch.api.jobtechdev.se/search"

    async def fetch(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        # Bygg en enkel OR-query utan specialtecken
        query = " OR ".join(KEYWORDS)

        headers = {
            "User-Agent": settings.af_user_agent,
            "Accept": "application/json",
        }
        if settings.jobtech_api_key:
            headers["api-key"] = settings.jobtech_api_key

        params = {
            "q": query,
            "limit": limit,
            "offset": offset,
        }

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.get(self.base_url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            log.exception(f"[AF] Request failed: {e}")
            return []

        hits = data.get("hits") or []
        log.info(f"[AF] {len(hits)} hits for q='{params['q']}'")

        jobs: List[Dict[str, Any]] = []
        for hit in hits:
            title = (hit.get("headline") or "").strip()
            title_l = title.lower()

            # Filtrera titlar som innehåller 'chef'
            if any(bad in title_l for bad in TITLE_BLOCK):
                continue

            employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
            wp = (hit.get("workplace_addresses") or [{}])[0] or {}
            city = (wp.get("municipality") or "").strip()
            region = (wp.get("region") or "").strip()

            jobs.append(
                {
                    "source": self.name,
                    "external_id": str(hit.get("id") or ""),
                    "title": title,
                    "employer": employer,
                    "city": city,
                    "region": region,
                    "published_at": _parse_published(hit.get("publication_date")),
                    "description": _flatten_description(hit),
                    "url": (hit.get("application_details") or {}).get("url")
                    or hit.get("webpage_url")
                    or "",
                }
            )

        return jobs
