from typing import Dict, List

# Kartläggning från UI-roll -> sökord mot AF
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
