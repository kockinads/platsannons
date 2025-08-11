from typing import AsyncIterator, Dict, Any

class JobProvider:
    name = "base"
    async def fetch(self, query: dict) -> AsyncIterator[Dict[str, Any]]:
        raise NotImplementedError

ROLE_KEYWORDS = {
    "kock": ["kock", "chef"],
    "köksbiträde": ["köksbiträde", "kitchen assistant"],
    "diskpersonal": ["diskare", "diskpersonal", "steward"],
    "serveringspersonal": ["servitör", "servitris", "serveringspersonal", "waiter", "waitress", "server"],
    "bartender": ["bartender", "bar"],
    "roddare": ["roddare", "runner"],
    "hovmästare": ["hovmästare", "maitre", "maître", "head waiter"],
    "köksmästare": ["köksmästare", "head chef", "chef de cuisine"],
    "souschef": ["souschef", "sous chef"],
    "1:e kock": ["förstekock", "1:e kock", "first cook"],
    "1:e servis": ["försteservis", "1:e servis", "head waiter"],
}
