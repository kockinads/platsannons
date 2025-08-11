import httpx
from datetime import datetime
from typing import AsyncIterator, Dict, Any
from .base import JobProvider, ROLE_KEYWORDS
from ..settings import settings

class AFProvider(JobProvider):
    name = "arbetsformedlingen"

    async def fetch(self, query: dict) -> AsyncIterator[Dict[str, Any]]:
        roles = query.get("roles", [])
        keywords = []
        for r in roles:
            keywords += ROLE_KEYWORDS.get(r, [])
        q = " ".join(sorted(set(keywords))) if keywords else "kock OR servitör OR bartender"

        region = query.get("region")
        municipality = query.get("city")

        params = {"q": q, "limit": 100}
        if region:
            params["region"] = region
        if municipality:
            params["municipality"] = municipality

        headers = {"User-Agent": settings.af_user_agent, "Accept": "application/json"}
        url = f"{settings.af_base_url}/search"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            for hit in data.get("hits", []):
                job = {
                    "external_id": str(hit.get("id")),
                    "title": hit.get("headline", ""),
                    "employer": (hit.get("employer", {}) or {}).get("name", "Okänd arbetsgivare"),
                    "city": (hit.get("workplace_addresses", [{}])[0] or {}).get("municipality", ""),
                    "region": (hit.get("workplace_addresses", [{}])[0] or {}).get("region", ""),
                    "published_at": hit.get("publication_date"),
                    "description": hit.get("description", ""),
                    "url": (hit.get("application_details", {}) or {}).get("url", hit.get("webpage_url", "")),
                }
                if job["published_at"]:
                    job["published_at"] = datetime.fromisoformat(job["published_at"].replace("Z", "+00:00"))
                else:
                    job["published_at"] = datetime.utcnow()
                yield job
