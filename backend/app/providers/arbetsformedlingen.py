import httpx
import re
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any, List
from .base import ROLE_KEYWORDS
from ..settings import settings
import logging

log = logging.getLogger("uvicorn.error")

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

def _parse_published(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()

def _norm(s: str) -> str:
    return (s or "").lower()

# Inkludera bara restaurang/kök/matsal/bar (ej café/barista)
INCLUDE_TERMS = [
    r"\bkock\b", r"\bkockar\b", r"\brestaurangkock\b", r"\bköksbiträde\b",
    r"\bköksmästare\b", r"\bkökschef\b", r"\bsouschef\b", r"\b1:?e?\s*kock\b",
    r"\bförstekock\b", r"\bcommis\b", r"\bkallskänk(?:a)?\b", r"\bkökspersonal\b",
    r"\bvarmkök\b", r"\bkallkök\b",
    r"\bpizzabagare\b", r"\bpizzabakare\b",
    r"\bservitör\b", r"\bservitris\b", r"\bserveringspersonal\b",
    r"\bhovmästare\b", r"\bsommelier\b", r"\bbartender\b", r"\bbarpersonal\b",
    r"\bbarchef\b", r"\brestaurangchef\b", r"\brestaurangvärd(?:inna)?\b",
]
EXCLUDE_TERMS = [
    r"\b(field\s*service|servicetekniker|tekniker|elektriker|mekaniker)\b",
    r"\b(it|support|help\s*desk|service\s*desk|nätverk|system(?:adm|utv|tekniker)?)\b",
    r"\b(hr|recruit(?:er|ing)|talent|business\s*partner|partner\s*manager)\b",
    r"\bshop\s*assistant\b|\bbutik(?:schef|ssäljare|säljare)\b",
    r"\blager\b|\bwarehouse\b|\btruckförare\b",
    r"\bfastighet(?:sskötare|stekniker)?\b|\bdrifttekniker\b",
    r"\bkoordinator\b|\bcoordinator\b|\bprojektledare\b",
    r"\benhetschef\b|\bverksamhetschef\b|\bplatschef\b(?!\s*restaurang)",
    r"\bcafé\b|\bbarista\b",
    r"\bstäd\b|\blokalvård\b",
    r"\bsjuksköterska\b|\bundersköterska\b|\bvård\b",
]
INCLUDE_RE = re.compile("|".join(INCLUDE_TERMS), re.I)
EXCLUDE_RE = re.compile("|".join(EXCLUDE_TERMS), re.I)

def _is_relevant(title: str, desc: str) -> bool:
    t = _norm(title)
    d = _norm(desc)
    if not (INCLUDE_RE.search(t) or INCLUDE_RE.search(d)):
        return False
    if EXCLUDE_RE.search(t) or EXCLUDE_RE.search(d):
        return False
    # Stäng ute "chef" (manager) om det inte är köks-/restaurang-/barchef
    if re.search(r"\bchef\b", t) and not re.search(r"\b(kökschef|restaurangchef|barchef)\b", t):
        return False
    return True

class AFProvider:
    name = "arbetsformedlingen"

    async def fetch(self, query: dict) -> AsyncIterator[Dict[str, Any]]:
        roles = query.get("roles", []) or []
        keywords: List[str] = []
        for r in roles:
            keywords += ROLE_KEYWORDS.get(r, [])
        if keywords:
            q = " OR ".join(sorted(set(keywords)))
        else:
            q = ("kock OR kök OR köksbiträde OR köksmästare OR souschef OR restaurang "
                 "OR servering OR servitör OR servitris OR hovmästare OR bartender "
                 "OR barpersonal OR pizzabagare")

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
        log.info(f"HARVEST: AF returned {len(hits)} hits for q='{q}'")

        for hit in hits:
            employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
            wp = (hit.get("workplace_addresses") or [{}])[0] or {}
            city = wp.get("municipality") or ""
            region = wp.get("region") or ""
            title = hit.get("headline") or ""
            desc_text = _flatten_description(hit)

            if not _is_relevant(title, desc_text):
                continue

            yield {
                "external_id": str(hit.get("id") or ""),
                "title": title,
                "employer": employer,
                "city": city,
                "region": region,
                "published_at": _parse_published(hit.get("publication_date")),
                "description": desc_text,
                "url": (hit.get("application_details") or {}).get("url") or hit.get("webpage_url") or "",
            }
