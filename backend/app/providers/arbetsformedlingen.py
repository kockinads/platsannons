import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List

from ..settings import settings

PROVIDER_NAME = "arbetsformedlingen"

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

# Rollfilter: HORECA (inkl. pizzabagare) och uteslut chef (eng. "chef" som manager).
ROLE_KEYWORDS = [
    "kock", "kök", "köksbiträde", "köksmästare", "souschef",
    "restaurang", "servering", "servitör", "servitris",
    "hovmästare", "bartender", "barpersonal", "pizzabagare",
    "grillkock", "bagare", "kallskänk", "diskare"
]

# Titelfilter: tillåt bara rubriker som ser ut som branschroller
ALLOW_IN_TITLE = [
    "kock", "kök", "köksbiträde", "köksmästare", "souschef",
    "restaurang", "servering", "servitör", "servitris",
    "hovmästare", "bartender", "bar", "pizzabagare",
    "grillkock", "bagare", "kallskänk", "diskare"
]
# Hårda NEJ för att slippa brus (eng. chef = manager)
BLOCK_IN_TITLE = [
    "hr", "partner", "analyst", "elektriker", "shop assistant",
    "field service", "service desk", "coordinator", "engineer",
    "arbetsledare", "enhetschef", "partner manager", "service tekniker",
    "serviceelektriker", "chef "  # svenskt "chef " fångas separat om du vill
]

def _title_is_allowed(title: str) -> bool:
    t = (title or "").lower()
    # måste innehålla minst ett tillåtet ord
    if not any(w in t for w in ALLOW_IN_TITLE):
        return False
    # och får inte innehålla något blockat ord
    if any(b in t for b in BLOCK_IN_TITLE):
        return False
    # extra regel: engelska ordet "chef" får inte förekomma (manager)
    if " chef" in t or t.startswith("chef"):
        # men tillåt svenska souschef (som är köksroll)
        if "souschef" in t:
            return True
        return False
    return True

async def fetch(query: dict) -> List[Dict[str, Any]]:
    q = " OR ".join(sorted(set(ROLE_KEYWORDS)))
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
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    hits = data.get("hits") or []

    jobs: List[Dict[str, Any]] = []
    for hit in hits:
        title = hit.get("headline") or ""
        if not _title_is_allowed(title):
            continue

        employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
        wp = (hit.get("workplace_addresses") or [{}])[0] or {}
        city = wp.get("municipality") or ""
        region = wp.get("region") or ""
        url_click = (hit.get("application_details") or {}).get("url") or hit.get("webpage_url") or ""

        job = {
            "external_id": str(hit.get("id") or ""),
            "title": title,
            "employer": employer,
            "city": city,
            "region": region,
            "published_at": _parse_published(hit.get("publication_date")),
            "description": _flatten_description(hit),
            "url": url_click,
        }
        jobs.append(job)

    return jobs
