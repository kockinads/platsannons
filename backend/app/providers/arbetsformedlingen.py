from __future__ import annotations

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List
from ..settings import settings

TITLE_BLOCK = {"chef"}  # blocka om hela ordet "chef" förekommer i titeln

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

    def __init__(self) -> None:
        self.base_url = settings.af_base_url
        self.headers = {
            "User-Agent": settings.af_user_agent,
            "Accept": "application/json",
        }
        if settings.jobtech_api_key:
            self.headers["api-key"] = settings.jobtech_api_key

    def fetch(self) -> List[Dict[str, Any]]:
        # Bred men enkel sökning för volym
        query = "kock"
        limit = 100
        offset = 0
        all_jobs: List[Dict[str, Any]] = []

        with httpx.Client(timeout=30) as client:
            while True:
                params = {"q": query, "limit": limit, "offset": offset}
                resp = client.get(self.base_url, params=params, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
                hits = data.get("hits") or []
                if not hits:
                    break

                for hit in hits:
                    title = (hit.get("headline") or "").strip()
                    # blocka titlar som innehåller hela ordet "chef"
                    title_words = {w.strip(",.!?;:()").lower() for w in title.split()}
                    if TITLE_BLOCK & title_words:
                        continue

                    employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
                    wp = (hit.get("workplace_addresses") or [{}])[0] or {}
                    city = (wp.get("municipality") or "").strip()
                    region = (wp.get("region") or "").strip()

                    all_jobs.append({
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

                # nästa sida
                if len(hits) < limit:
                    break
                offset += limit

        return all_jobs
