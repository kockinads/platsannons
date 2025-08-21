import httpx
from datetime import datetime
from typing import List, Dict, Any

# Blockera titlar som innehåller "chef"
TITLE_BLOCK = ["chef"]

# Säkra sökord (inga specialtecken som "1:e", etc.)
KEYWORDS = [
    "kock","restaurangkock","kök","köksbiträde","köksmästare","souschef",
    "pizzabagare","kallskänk","kallkök","varmkök",
    "servitör","servitris","serveringspersonal","hovmästare",
    "bartender","barpersonal","sommelier","restaurang"
]

AF_BASE_URL = "https://jobsearch.api.jobtechdev.se/search"
USER_AGENT = "platsannons-aggregator/1.0"

def _flatten_description(hit: Dict[str, Any]) -> str:
    desc = hit.get("description")
    if isinstance(desc, dict):
        parts = []
        for key in ("text","company_information","needs","requirements","conditions"):
            v = desc.get(key)
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
        return "\n\n".join(parts)
    return desc or ""

def _parse_date(v: str | None) -> datetime:
    try:
        return datetime.fromisoformat(v.replace("Z","+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()

def _chunk(lst: List[str], size: int) -> List[List[str]]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]

class AFProvider:
    name = "arbetsformedlingen"

    def __init__(self):
        self.client = httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    def fetch(self) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        # Kör i små batchar för att undvika 400 pga för långa queries
        for batch in _chunk(KEYWORDS, 8):
            q = " OR ".join(batch)
            offset = 0
            while True:
                params = {"q": q, "limit": 100, "offset": offset}
                resp = self.client.get(AF_BASE_URL, params=params)
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError:
                    # Skippa batchen om AF svarar 400 (hellre fortsätt än att krascha)
                    break
                data = resp.json()
                hits = data.get("hits") or []
                if not hits:
                    break

                for h in hits:
                    title = (h.get("headline") or "").strip()
                    if any(b in title.lower() for b in TITLE_BLOCK):
                        continue

                    employer = (h.get("employer") or {}).get("name") or "Okänd arbetsgivare"
                    wp = (h.get("workplace_addresses") or [{}])[0] or {}
                    jobs.append({
                        "source": self.name,
                        "external_id": str(h.get("id") or ""),
                        "title": title,
                        "employer": employer,
                        "city": (wp.get("municipality") or "").strip(),
                        "region": (wp.get("region") or "").strip(),
                        "published_at": _parse_date(h.get("publication_date")),
                        "description": _flatten_description(h),
                        "url": (h.get("application_details") or {}).get("url") or h.get("webpage_url") or "",
                    })
                # nästa sida
                offset += 100
        return jobs
