from typing import Dict, List

# Kartläggning från frontendens "roller" till sökord vi skickar till AF
# (Du kan gärna utöka listorna senare.)
ROLE_KEYWORDS: Dict[str, List[str]] = {
    "kock": [
        "kock", "kockar", "restaurangkock", "köksbiträde", "köksmästare",
        "kökschef", "souschef", "1:e kock", "förstekock", "commis", "kallskänk",
        "kallskänka", "kökspersonal", "matlagning", "restaurangkök", "varmkök", "kallkök",
        "pizzabagare", "pizzabagare sökes", "pizzabakare"
    ],
    "servis": [
        "servitör", "servitris", "serveringspersonal", "hovmästare", "sommelier",
        "bartender", "barpersonal", "barchef", "restaurangchef", "restaurangvärd",
        "restaurangvärdinna"
    ],
    "bartender": ["bartender", "barpersonal", "barchef", "mixologist"],
    "pizzabagare": ["pizzabagare", "pizzabakare"],
    # Lägg fler nycklar/roller om du vill exponera dem i UI:t
}
