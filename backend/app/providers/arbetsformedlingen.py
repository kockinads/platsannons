# backend/app/providers/arbetsformedlingen.py
from __future__ import annotations
import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List
from ..settings import settings
from .base import JobProvider  # finns som tom bas-klass
import logging

log = logging.getLogger("uvicorn.error")

# Bred sökfråga (hellre fångar för mycket än för lite; vi filtrerar lite mjukare nedan)
ROLE_QUERY = (
    "kock OR kök OR köksbiträde OR köksmästare OR souschef OR restaurang OR "
    "servering OR servitör OR servitris OR hovmästare OR bartender OR barpersonal OR pizzabagare"
)

# Tillåt-ord (substratmatchning i titel, ej bara hela ord)
TITLE_ALLOW = [
    "kock", "grillkock", "pizzabag", "köksbitr", "köksmäst", "souschef",
    "servitör", "servitris", "serverings", "hovmäst", "bartender", "barpersonal",
    "sommelier", "diskare", "diskpersonal", "kökschef", "förstekock", "commis",
    "kallskänk", "kallskänka", "kökspersonal"
]

# Blockera uppenbart irrelevanta rubriker (kort lista – vi kan skruva sen)
TITLE_BLOCK = [
    "hr", "rekryter", "elektriker", "it", "analyst", "coordinator", "manager", "partner",
    "tekniker", "enhetschef", "field service", "service desk", "butik", "shop assistant"
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
        log.info(f"HARVEST: AF raw hits = {len(hits)} for q='{params['q']}'")

        kept: List[Dict[str, Any]] = []
        dropped_titles: List[str] = []

        for hit in hits:
            title = (hit.get("headline") or "").strip()
            tl = title.lower()

            # Hårda blockord (om någon av fraserna finns som substring i titel → droppa)
            if any(b in tl for b in TITLE_BLOCK):
                dropped_titles.append(title)
                continue

            # Minst ett tillåt-ord i titeln, annars är den troligen fel (mjuk filtrering)
            if not any(allow in tl for allow in TITLE_ALLOW):
                dropped_titles.append(title)
                continue

            employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
            wp = (hit.get("workplace_addresses") or [{}])[0] or {}
            city = (wp.get("municipality") or "").strip()
            region = (wp.get("region") or "").strip()

            kept.append({
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

        log.info(f"HARVEST: kept={len(kept)} dropped={len(dropped_titles)}")
        if dropped_titles:
            log.info("HARVEST: examples of dropped titles: " + " | ".join(dropped_titles[:10]))

        return kept
