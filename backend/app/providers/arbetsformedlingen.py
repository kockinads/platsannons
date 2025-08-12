import re
import httpx
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any, List
from .base import JobProvider
from ..settings import settings
import logging

log = logging.getLogger("uvicorn.error")

# -----------------------------
# Hjälpfunktioner
# -----------------------------

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


# -----------------------------
# Filtreringsregler
# -----------------------------

# Inkludera – ord i titel/beskrivning som markerar relevanta roller (kök, matsal, bar).
INCLUDE_PATTERNS = [
    r"\b1:\s*e\s*kock\b",              # 1:e kock
    r"\bförste\s*kock\b",
    r"\bkock(ar)?\b",
    r"\bköks?mästare\b",
    r"\bköks?chef\b",
    r"\bsous\s*chef\b",
    r"\bchef\s*de\s*partie\b",
    r"\bcommis\b",
    r"\bkallskänk(a|e)?\b",
    r"\bköks?biträde\b",
    r"\bköks?personal\b",
    r"\bdiskare\b",
    r"\bserveringspersonal\b",
    r"\bservit(ör|ris)\b",
    r"\bhovmästare\b",
    r"\bbartender\b",
    r"\bbarpersonal\b",
    r"\bbarback\b",
    r"\brunner\b",
    r"\bsommelier\b",
    r"\bpizzabagare\b",
]

INCLUDE_RE = re.compile("|".join(INCLUDE_PATTERNS), re.I | re.U)

# Kontextord – minst ett bör finnas för att undvika “service/teknik”-felträffar.
CONTEXT_WORDS = [
    "restaurang", "servering", "matsal", "kök", "koks", "köks", "a la carte", "à la carte", "gäst", "bar",
]
CONTEXT_RE = re.compile("|".join(rf"\b{re.escape(w)}\b" for w in CONTEXT_WORDS), re.I | re.U)

# Exkludera – ord som signalerar icke-relevanta jobb.
EXCLUDE_WORDS = [
    # Teknik/IT/Service
    "field service", "servicetekniker", "tekniker", "elektriker", "engineer", "developer",
    "analyst", "support", "helpdesk", "it", "network", "teknisk",
    # Ledning/HR/adm (ej restaurangspecificerat)
    "enhetschef", "verksamhetschef", "platschef", "arbetsledare", "manager", "coordinator",
    "partner manager", "project manager", "business partner", "hr", "talent", "recruiter",
    # Butik/logistik/fastighet
    "shop assistant", "butik", "retail", "lager", "warehouse", "logistik", "chaufför",
    "vaktmästare", "fastighet",
    # Städ/vård/skola
    "städ", "lokalvård", "undersköterska", "sjuksköterska", "lärare", "förskola", "barnskötare",
    # Kundtjänst/sälj
    "kundtjänst", "callcenter", "sales", "säljare", "account manager",
    # Café/Barista (ska bort enligt krav)
    "barista", "caf\u00e9", "café", "fik", "konditor", "bagare",  # OBS: pizzabagare hanteras separat som positivt ord
]

EXCLUDE_RE = re.compile("|".join(re.escape(w) for w in EXCLUDE_WORDS), re.I | re.U)

# Specialregel för engelska "chef": blocka om det inte tydligt är köksrelaterat
ALLOW_AROUND_CHEF = re.compile(r"(köks|kök|sous|restaurang|servering|hov|bar)", re.I | re.U)
CHEF_ALONE_RE = re.compile(r"\bchef\b", re.I | re.U)


def _is_relevant(title: str, description: str) -> bool:
    t = (title or "").strip()
    d = (description or "").strip()
    blob = f"{t}\n{d}".lower()

    # Exkludera om svartlistat ord finns
    if EXCLUDE_RE.search(blob):
        return False

    # Blocka "chef" när det inte är köks-/serveringsrelaterat (t.ex. enhetschef, servicechef)
    if CHEF_ALONE_RE.search(t) and not ALLOW_AROUND_CHEF.search(t):
        return False

    # Måste matcha minst ett inkluderande mönster
    if not INCLUDE_RE.search(blob):
        return False

    # Kräver även minst ett kontextord för att minska felträffar (service/teknik)
    if not CONTEXT_RE.search(blob):
        return False

    return True


class AFProvider(JobProvider):
    name = "arbetsformedlingen"

    async def fetch(self, query: dict) -> AsyncIterator[Dict[str, Any]]:
        """
        Hämtar upp till 100 annonser från AF och filtrerar till
        kök/matsal/bar (exkl. café/barista), inkl. alla kock-varianter
        och pizzabagare.
        """
        # Vi söker brett (AF rankar ändå). Filtreringen sker lokalt.
        params = {"q": "kock OR servitör OR bartender OR restaurang OR kök OR matsal OR bar", "limit": 100}

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
        log.info(f"HARVEST: AF returned {len(hits)} hits (before filtering)")

        kept = 0
        for hit in hits:
            employer = (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare"
            wp = (hit.get("workplace_addresses") or [{}])[0] or {}
            city = wp.get("municipality") or ""          # ibland tomt
            region = wp.get("region") or ""              # ibland tomt

            title = hit.get("headline") or ""
            description = _flatten_description(hit)

            # Filtrera bort irrelevanta
            if not _is_relevant(title, description):
                continue

            job = {
                "external_id": str(hit.get("id") or ""),
                "title": title,
                "employer": employer,
                "city": city,
                "region": region,
                "published_at": _parse_published(hit.get("publication_date")),
                "description": description,  # alltid sträng
                "url": (hit.get("application_details") or {}).get("url") or hit.get("webpage_url") or "",
            }
            kept += 1
            yield job

        log.info(f"HARVEST: AF kept {kept} / {len(hits)} after filtering")
