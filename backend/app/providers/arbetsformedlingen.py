from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from ..settings import settings
from .base import ROLE_KEYWORDS

log = logging.getLogger("uvicorn.error")

# Tillåtna titel-ord (måste finnas minst ett)
TITLE_ALLOW = {
    "kock", "grillkock", "pizzabagare", "köksbiträde", "köksmästare", "souschef",
    "servitör", "servitris", "serveringspersonal", "hovmästare", "bartender", "barpersonal",
    "sommelier", "kallskänk", "kallskänka"
}

# Ord som blockerar annonsen om de finns i titeln
TITLE_BLOCK = {
    "chef", "manager", "partner", "hr", "rekryterare", "rekrytering",
    "it", "elektriker", "tekniker", "analyst", "analytiker", "coordinator",
    "enhetschef", "arbetsledare", "service", "field", "shop", "assistant",
    "desk"
}


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
        return (
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
    except Exception:
        return datetime.utcnow()


def _build_query_from_roles(roles: List[str] | None) -> str:
    """
    Bygger en AF-sökfråga (OR-kedjad) från givna roller utifrån ROLE_KEYWORDS.
    Om inga roller anges används en bred standard för att inte missa relevanta annonser.
    """
    if not roles:
        seed = [
            "kock", "köksbiträde", "köksmästare", "souschef",
            "servitör", "servitris", "hovmästare", "bartender",
            "barpersonal", "pizzabagare", "kallskänk", "kallskänka",
        ]
        return " OR ".join(seed)

    words: List[str] = []
    for r in roles:
        words += ROLE_KEYWORDS.get(r, [])
    # unika ord, enklast med dict.fromkeys för stabil ordning
    unique = list(dict.fromkeys(w.lower() for w in words if w.strip()))
    if not unique:
        return "kock OR servitör OR bartender OR pizzabagare"
    return " OR ".join(unique)


class AFProvider:
    name = "arbetsformedlingen"

    async def fetch(self, roles: List[str] | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        q = _build_query_from_roles(roles)
        params = {"q": q, "limit": limit}
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
            tl = title.lower()

            # Blockera uppenbart orelevanta roller
            if any(b in tl.split() for b in TITLE_BLOCK):
                continue

            # Kräver minst ett "giltigt" ord i titeln (för att inte missa varianter som grillkock m.m.)
            if not any(a in tl for a in TITLE_ALLOW):
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
