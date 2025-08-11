import httpx
from datetime import datetime
from typing import AsyncIterator, Dict, Any
from .base import JobProvider, ROLE_KEYWORDS
from ..settings import settings

class AFProvider(JobProvider):
    name = "arbetsformedlingen"

    async def fetch(self, query: dict) -> AsyncIterator[Dict[str, Any]]:
        # Bygg en enkel sökfråga om roller saknas
        roles = query.get("roles", [])
        keywords = []
        for r in roles:
            keywords += ROLE_KEYWORDS.get(r, [])
        q = " ".join(sorted(set(keywords))) if keywords else "kock OR servitör OR bartender"

        # Håll parametrarna snäva och giltiga
        params = {"q": q, "limit": 100}

        headers = {
            "User-Agent": settings.af_user_agent,
            "Accept": "application/json",
        }
        # Skicka API-nyckel om du har en
        if getattr(settings, "jobtech_api_key", ""):
            headers["api-key"] = settings.jobtech_api_key

        url = f"{settings.af_base_url}/search"

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            for hit in data.get("hits", []):
                job = {
                    "external_id": str(hit.get("id")),
                    "title": hit.get("headline", "") or "",
                    "employer": (hit.get("employer") or {}).get("name", "Okänd arbetsgivare"),
                    "city": (hit.get("workplace_addresses") or [{}])[0].get("municipality", "") or "",
                    "region": (hit.get("workplace_addresses") or [{}])[0].get("region", "") or "",
                    "published_at": hit.get("publication_date"),
                    "description": hit.get("description", "") or "",
                    "url": (hit.get("application_details") or {}).get("url") or hit.get("webpage_url", "") or "",
                }
                ts = job["published_at"]
                if ts:
                    job["published_at"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    job["published_at"] = datetime.utcnow()
                yield job
