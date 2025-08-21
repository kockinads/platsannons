from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from ..settings import settings
from .base import ROLE_KEYWORDS

log = logging.getLogger("uvicorn.error")

AF_BASE_URL = settings.af_base_url or "https://jobsearch.api.jobtechdev.se/search"

# Termer vi absolut inte vill skicka
BLOCK_TOKENS = {
    "1:e",  # orsakade 400
}

# tillåt svenska bokstäver + a-z0-9 + bindestreck
def _safe_token(tok: str) -> str:
    tok = tok.strip()
    if not tok or tok.lower() in BLOCK_TOKENS:
        return ""
    # rensa bort tecken som kan sabba queryn (kolon etc)
    cleaned = []
    for ch in tok:
        if ch.isalnum() or ch in "- " or ch in "åäöÅÄÖ":
            cleaned.append(ch)
        # allt annat slängs (t.ex. ':', '/', '"', etc.)
    t = "".join(cleaned).strip()
    # släng en- eller tvåteckens skräp
    return t if len(t) >= 3 else ""

def _build_queries() -> List[str]:
    """
    Bygger en lista av OR-strängar i flera chunkar så vi inte får för långa
    queries, och så att vi undviker tokiga tecken.
    """
    # plocka alla tokens från base.py
    raw_tokens: List[str] = []
    for _, toks in ROLE_KEYWORDS.items():
        raw_tokens.extend(toks)

    # sanera & unika
    toks = []
    seen = set()
    for t in raw_tokens:
        s = _safe_token(t.lower())
        if s and s not in seen:
            seen.add(s)
            toks.append(s)

    # chunkning: max ca 10–12 termer per query för att vara safe
    chunks: List[List[str]] = []
    CHUNK_SIZE = 12
    for i in range(0, len(toks), CHUNK_SIZE):
        chunks.append(toks[i : i + CHUNK_SIZE])

    queries: List[str] = []
    for chunk in chunks:
        # citera multiord (t.ex. "kall kök" -> "kall kök"), men de flesta är en-ord
        parts = [f'"{t}"' if " " in t else t for t in chunk]
        queries.append(" OR ".join(parts))
    return queries

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
        headers = {
            "User-Agent": settings.af_user_agent,
            "Accept": "application/json",
        }
        if settings.jobtech_api_key:
            headers["api-key"] = settings.jobtech_api_key

        queries = _build_queries()
        jobs: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=25) as client:
            for q in queries:
                params = {"q": q, "limit": 100, "offset": 0}
                try:
                    log.info(f"[AF] query: {q}")
                    resp = await client.get(AF_BASE_URL, params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    log.error(f"[AF] Request failed: {e}")
                    continue

                hits = data.get("hits") or []
                for hit in hits:
                    title = (hit.get("headline") or "").strip()
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

        log.info(f"[AF] total jobs collected: {len(jobs)}")
        return jobs
