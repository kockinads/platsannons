import httpx
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any
from .base import JobProvider, ROLE_KEYWORDS
from ..settings import settings
import logging

log = logging.getLogger("uvicorn.error")

class AFProvider(JobProvider):
    name = "arbetsformedlingen"

    async def fetch(self, query: dict) -> AsyncIterator[Dict[str, Any]]:
        roles = query.get("roles", [])
        keywords = []
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
            async with httpx.AsyncClient(timeout=20) as client:
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
            city = wp.get("municipality") or ""
            region = wp.get("region") or ""
            published_raw = hit.get("publication_date")

            if published_raw:
                try:
                    published_dt = (
                        datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                        .astimezone(timezone.utc)
                        .replace(tzinfo=None)
                    )
                except Exception:
                    published_dt = datetime.utcnow()
            else:
                published_dt = datetime.utcnow()

            url_field = (hit.get("application_details") or {}).get("url") or hit.get("webpage_url") or ""

            job = {
                "external_id": str(hit.get("id")),
                "title": hit.get("headline") or "",
                "employer": employer,
                "city": city,
                "region": region,
                "published_at": published_dt,
                "description": hit.get("description") or "",
                "url": url_field,
            }
            yield job
