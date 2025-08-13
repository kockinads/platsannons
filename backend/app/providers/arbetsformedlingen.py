# backend/app/providers/arbetsformedlingen.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from ..settings import settings
from .base import JobProvider

log = logging.getLogger("uvicorn.error")

# Söktermer (brett inom kök/restaurang/bar)
ROLE_QUERY = (
    "kock OR kök OR köksbiträde OR köksmästare OR souschef OR restaurang OR "
    "servering OR servitör OR servitris OR hovmästare OR bartender OR barpersonal OR pizzabagare"
)

# Titelfilter
TITLE_ALLOW = {
    "kock", "grillkock", "pizzabagare", "köksbiträde", "köksmästare", "souschef",
    "servitör", "servitris", "serveringspersonal", "hovmästare", "bartender", "barpersonal",
}
TITLE_BLOCK = {"chef", "manager", "partner", "hr", "it", "elektriker", "tekniker", "analyst", "coordinator"}


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


class AFProvider(JobProvider):
    name = "arbetsformedlingen"

    async def fetch(self) -> List[Dict[str, Any]]:
        params = {"q": ROLE_QUERY, "limit": 100}
        headers = {
            "User-Agent": settings.af_user_agent,
            "Accept": "application/json",
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
            title_l = title.lower()

            # blocka ord som "chef", "hr", etc
            if any(b in title_l.split() for b in TITLE_BLOCK):
                continue
            # kräver att någon tillåten term finns i titeln
            if not any(word in title_l for word in TITLE_ALLOW):
                continue

            employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
            wp = (hit.get("workplace_addresses") or [{}])[0] or {}
            city = (wp.get("municipality") or "").strip()
            region = (wp.get("region") or "").strip()

            jobs.append({
                "source": self.name,
                "external_id": str(hit.get("id") or ""),
                "title": title,
                "employer": employer,
                "city": city,
                "region": region,
                "published_at": _parse_published(hit.get("publication_date")),
                "description": _flatten_description(hit),
                "url": (hit.get("application_details") or {}).get("url") or hit.get("webpage_url") or "",
            })
        return jobs
