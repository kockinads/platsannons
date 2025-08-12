import httpx
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any, List, Set
from .base import JobProvider, ROLE_KEYWORDS
from ..settings import settings
import logging

log = logging.getLogger("uvicorn.error")

def _flatten_description(hit: Dict[str, Any]) -> str:
    """
    AF:s API kan returnera description som dict:
      { "text": "...", "company_information": "...", "needs": "...", ... }
    Vi syr ihop alla strängfält till en enda text.
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
    return ""

def _parse_published(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.utcnow()
    try:
        # ISO 8601, ibland med Z
        return (
            datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
    except Exception:
        return datetime.utcnow()

def _pick_city(hit: Dict[str, Any]) -> str:
    wp_list = hit.get("workplace_addresses") or []
    if isinstance(wp_list, list) and wp_list:
        wp = wp_list[0] or {}
        # prova kommunnamn → city → ort
        return (
            wp.get("municipality")
            or wp.get("city")
            or wp.get("address")
            or ""
        )
    return ""

def _pick_region(hit: Dict[str, Any]) -> str:
    wp_list = hit.get("workplace_addresses") or []
    if isinstance(wp_list, list) and wp_list:
        wp = wp_list[0] or {}
        return wp.get("region") or wp.get("county") or ""
    return ""

def _pick_url(hit: Dict[str, Any]) -> str:
    app = hit.get("application_details") or {}
    return app.get("url") or hit.get("webpage_url") or ""

class AFProvider(JobProvider):
    name = "arbetsformedlingen"

    async def fetch(self, query: dict) -> AsyncIterator[Dict[str, Any]]:
        """
        Kör flera sökningar med bredare nyckelord och deduplar på annons-ID.
        Om UI skickar in 'roles' används dessa för att bygga söksträng, annars fallback.
        """
        # 1) Bygg nyckelord från roller (om UI skickar in sådana)
        roles = query.get("roles", [])
        keywords_from_roles: List[str] = []
        for r in roles:
            keywords_from_roles += ROLE_KEYWORDS.get(r, [])

        # 2) Basnyckelord (bred svenska mix som fångar AF-annonser typ "SSP – kock")
        base_sv_keywords = [
            "kock", "kock*", "köksbiträde", "koksbiträde", "koksbitrade",  # felstav/varianter
            "kökschef", "souschef",
            "servitör", "servitris", "serveringspersonal", "servering",
            "bartender", "barpersonal",
            "pizzabagare", "bagare", "konditor",
            # några generiska för restaurang som ibland används i rubriker
            "restaurang", "kitchen", "chef"  # (chef kan ge brus men hjälper vissa engelska rubriker)
        ]

        # 3) Om roller finns → börja med dem; annars bred baslista
        if keywords_from_roles:
            first_query = " OR ".join(sorted(set(keywords_from_roles)))
        else:
            first_query = " OR ".join(base_sv_keywords)

        # 4) Kompletterande söksträngar att prova om första inte fångar allt
        extra_queries = [
            # snävare fokus på kock
            "kock OR kökschef OR souschef OR köksbiträde",
            # mer service
            "servitör OR servitris OR serveringspersonal OR bartender",
        ]

        # 5) Om arbetsgivare råkar vara känd (t.ex. SSP) – hjälp AF att hitta dem i titlar/beskrivning
        #    Vi lägger bara till detta som en extra sökning; det gör ingen skada om det inte träffar.
        extra_queries.append("SSP OR 'Scandinavian Service Partner'")

        # 6) Förbered HTTP
        headers = {
            "User-Agent": settings.af_user_agent or "platsannons-aggregator/1.0",
            "Accept": "application/json",
            # "Accept-Language": "sv-SE"  # kan aktiveras vid behov
        }
        if getattr(settings, "jobtech_api_key", ""):
            headers["api-key"] = settings.jobtech_api_key

        base_url = settings.af_base_url.rstrip("/")
        search_url = f"{base_url}/search"

        async def _search(client: httpx.AsyncClient, q: str) -> List[Dict[str, Any]]:
            params = {"q": q, "limit": 100}
            try:
                resp = await client.get(search_url, params=params, headers=headers)
                if resp.status_code >= 400:
                    log.error(f"AF API error {resp.status_code} for q='{q}': {resp.text[:300]}")
                    return []
                data = resp.json()
                return data.get("hits") or []
            except Exception as e:
                log.exception(f"AF request failed for q='{q}': {e}")
                return []

        all_hits: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                # Första (huvud-)sökningen
                primary_hits = await _search(client, first_query)
                all_hits.extend(primary_hits)

                # Extra sökningar – bra för att fånga annonser som slunkit förbi
                for q in extra_queries:
                    extra_hits = await _search(client, q)
                    all_hits.extend(extra_hits)
        except Exception as e:
            log.exception(f"AF batch search failed: {e}")
            return

        # Dedupla och generera job-objekt
        unique_hits: List[Dict[str, Any]] = []
        for h in all_hits:
            hid = str(h.get("id") or "")
            if not hid or hid in seen_ids:
                continue
            seen_ids.add(hid)
            unique_hits.append(h)

        log.info(f"HARVEST: AF collected {len(unique_hits)} unique hits after merging queries")

        for hit in unique_hits:
            job = {
                "external_id": str(hit.get("id") or ""),
                "title": hit.get("headline") or "",
                "employer": (hit.get("employer") or {}).get("name") or "Okänd arbetsgivare",
                "city": _pick_city(hit),
                "region": _pick_region(hit),
                "published_at": _parse_published(hit.get("publication_date")),
                "description": _flatten_description(hit),
                "url": _pick_url(hit),
            }
            yield job
