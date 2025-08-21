# backend/app/providers/arbetsformedlingen.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from ..settings import settings
from .base import ROLE_KEYWORDS  # vi använder roll->sökord-kartan för att bygga OR-sökning

log = logging.getLogger("uvicorn.error")

# Bygg en bred OR-query av alla roll-sökord vi har i base.py
# Ex: (kock OR köksbiträde OR ...) OR (servitör OR servitris ...) ...
def _build_role_query() -> str:
    terms: List[str] = []
    for words in ROLE_KEYWORDS.values():
        terms.extend(words)
    # Säkra unika och icke-tomma ord
    uniq = [w.strip() for w in sorted(set(terms)) if w and w.strip()]
    # Jobtech tolkar mellanslag som AND, så vi använder explicit OR
    return " OR ".join(uniq)

# Liten lista för enkel title-block (brus som ofta inte är HORECA-roller)
TITLE_BLOCK = {
    "hr", "partner", "manager", "chefrekryterare", "rekryterare",
    "it", "elektriker", "tekniker", "analyst", "koordinator", "coordinator",
}

# En del tillåtna nyckelord i titel (hjälper när beskrivningen är bred)
TITLE_ALLOW = {
    "kock", "grillkock", "restaurangkock", "köksbiträde", "köksmästare", "kökschef",
    "souschef", "commis", "kallskänk", "kallskänka", "kökspersonal", "varmkök", "kallkök",
    "pizzabagare", "pizzabakare",
    "servitör", "servitris", "serveringspersonal", "hovmästare",
    "sommelier", "bartender", "barpersonal", "barchef",
    "restaurangchef", "restaurangvärd", "restaurangvärdinna",
}

def _flatten_description(hit: Dict[str, Any]) -> str:
    desc = hit.get("description")
    if isinstance(desc, dict):
        parts: List[str] = []
        for key in ("text", "company_information", "needs", "requirements", "conditions"):
            v = desc.get(key)
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
        return "\n\n".join(parts)
    if isinstance(desc, str):
        return desc
    return ""

def _parse_published(v: str | None) -> datetime:
    if not v:
        return datetime.utcnow()
    try:
        # "2024-05-15T13:37:00Z" -> naive UTC
        return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()

class AFProvider:
    name = "arbetsformedlingen"

    async def fetch(self) -> List[Dict[str, Any]]:
        q = _build_role_query()
        params = {
            "q": q,
            "limit": 100,     # hämta rejält med träffar
            "offset": 0,
        }
        headers = {
            "User-Agent": settings.af_user_agent,
            "Accept": "application/json",
        }
        if settings.jobtech_api_key:
            headers["api-key"] = settings.jobtech_api_key

        # ===== HÄMTA =====
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(settings.af_base_url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            log.exception(f"[AF] Request failed: {e}")
            return []

        hits: List[Dict[str, Any]] = data.get("hits") or []
        log.info(f"[AF] Hämtade totalt {len(hits)} träffar för q='{params['q'][:120]}{'...' if len(params['q'])>120 else ''}'")

        # ===== FILTRERA & RÄKNA ORSAKER =====
        reasons = {
            "no_headline": 0,
            "title_block": 0,
            "title_not_allowed": 0,
            "no_external_id": 0,
            "ok": 0,
        }

        jobs: List[Dict[str, Any]] = []
        for hit in hits:
            title = (hit.get("headline") or "").strip()
            if not title:
                reasons["no_headline"] += 1
                continue

            tl = title.lower()

            # blocka uppenbara icke-roller
            # vi blockar om *något* block-ord förekommer som helt ord i titeln
            if any(b in tl.split() for b in TITLE_BLOCK):
                reasons["title_block"] += 1
                continue

            # kräv att minst ett allow-ord finns i titeln (ganska snällt filter)
            if not any(kw in tl for kw in TITLE_ALLOW):
                reasons["title_not_allowed"] += 1
                continue

            ext_id = hit.get("id")
            if not ext_id:
                reasons["no_external_id"] += 1
                continue

            employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
            wp = (hit.get("workplace_addresses") or [{}])[0] or {}
            city = (wp.get("municipality") or "").strip()
            region = (wp.get("region") or "").strip()

            job = {
                "source": self.name,
                "external_id": str(ext_id),
                "title": title,
                "employer": employer,
                "city": city,
                "region": region,
                "published_at": _parse_published(hit.get("publication_date")),
                "description": _flatten_description(hit),
                "url": (hit.get("application_details") or {}).get("url") or hit.get("webpage_url") or "",
            }
            jobs.append(job)
            reasons["ok"] += 1

        # Summera och logga utfallet
        dropped = sum(v for k, v in reasons.items() if k != "ok")
        log.info(
            "[AF] Efter filter: sparas=%d, bortfiltrerade=%d "
            "(no_headline=%d, title_block=%d, title_not_allowed=%d, no_external_id=%d)",
            reasons["ok"], dropped,
            reasons["no_headline"], reasons["title_block"], reasons["title_not_allowed"], reasons["no_external_id"]
        )

        return jobs
