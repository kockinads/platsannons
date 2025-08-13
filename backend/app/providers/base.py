from typing import Dict, List, Any

class JobProvider:
    name: str = "base"

    async def fetch(self) -> List[Dict[str, Any]]:  # ska implementeras av providers
        raise NotImplementedError


# (Frivillig) kartläggning från UI-roll -> sökord mot AF.
# Ligger kvar här för ev. framtida behov.
ROLE_KEYWORDS: Dict[str, List[str]] = {
    "kock": [
        "kock", "kockar", "restaurangkock", "köksbiträde", "köksmästare",
        "kökschef", "souschef", "1:e kock", "förstekock", "commis", "kallskänk",
        "kallskänka", "kökspersonal", "matlagning", "restaurangkök", "varmkök", "kallkök",
        "pizzabagare", "pizzabakare"
    ],
    "servis": [
        "servitör", "servitris", "serveringspersonal", "hovmästare", "sommelier",
        "bartender", "barpersonal", "barchef", "restaurangchef", "restaurangvärd",
        "restaurangvärdinna"
    ],
    "bartender": ["bartender", "barpersonal", "barchef", "mixologist"],
    "pizzabagare": ["pizzabagare", "pizzabakare"],
}
