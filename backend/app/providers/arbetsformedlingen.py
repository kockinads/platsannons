import httpx
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any, List
from .base import JobProvider, ROLE_KEYWORDS
from ..settings import settings
import logging

log = logging.getLogger("uvicorn.error")

def _flatten_description(hit: Dict[str, Any]) -> str:
    """
    AF:s API returnerar ofta description som ett dict:
      { "text": "...", "company_information": "...", "needs": "...", ... }
    Vi syr ihop alla sträng-fält till en enda text.
    """
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
    return ""  # allt annat → tom text

def _parse_published(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.utcnow()
    try:
        # ISO 8601, ibland med Z
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()

class AFProvider(JobProvider):
    name = "arbetsformedlingen"

    async def fetch(self, query: dict) -> AsyncIterator[Dict[str, Any]]:
        # Bygg sökfråga av givna roller (fallback till några vanliga inom restaurang)
        roles = query.get("roles", [])
        keywords: List[str] = []
        for r in roles:
            keywords += ROLE_KEYWORDS.get(r, [])
        q = " ".join(sorted(set(keywords))) if keywords else "kock OR servitör OR bartender"

        params = {"q": q, "limit": 100}
        headers = {
            "User-Agent": settings.af_user_agent or "platsannons-aggregator/1.0",
            "Accept": "application/json",
        }
        if getattr(settings, "jobtech_api_key", ""):
            headers["api-key"] = settings.jobtech_api_key

        url = f"{settings.af_base_url.rstrip('/')}/search"

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code >= 400:
                    log.error(f"AF API error {resp.status_code}: {resp.text[:300]}")
                    return
                data = resp.json()
        except Exception as e:
            log.exception(f"AF request failed: {e}")
            return

        hits = data.get("hits") or []
        log.info(f"HARVEST: AF returned {len(hits)} hits")

        for hit in hits:
            employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
            wp = (hit.get("workplace_addresses") or [{}])[0] or {}
            city = wp.get("municipality") or ""          # ibland tomt
            region = wp.get("region") or ""              # ibland tomt

            job = {
                "external_id": str(hit.get("id") or ""),
                "title": hit.get("headline") or "",
                "employer": employer,
                "city": city,
                "region": region,
                "published_at": _parse_published(hit.get("publication_date")),
                "description": _flatten_description(hit),  # <-- alltid sträng
                "url": (hit.get("application_details") or {}).get("url") or hit.get("webpage_url") or "",
            }
            yield job
