import httpx
import logging

AF_URL = "https://jobsearch.api.jobtechdev.se/search"
# Vi blockerar alla annonser som innehåller "chef" i titeln
TITLE_BLOCK = ["chef"]

class AFProvider:
    def __init__(self):
        self.client = httpx.Client(timeout=30)

    def fetch(self):
        query = (
            "kock OR köksbiträde OR kallskänk OR serveringspersonal "
            "OR servitör OR servitris OR bartender OR hovmästare OR pizzabagare"
        )
        params = {
            "q": query,
            "limit": 100,
            "offset": 0,
        }

        try:
            resp = self.client.get(AF_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logging.error("[AF] Request failed: %s", e)
            return []

        jobs = []
        for hit in data.get("hits", []):
            title = hit.get("headline", "")
            employer = hit.get("employer", {}).get("name", "")
            url = hit.get("webpage_url", "")

            # Skippa alla jobb där titeln innehåller förbjudna ord
            if any(block.lower() in title.lower() for block in TITLE_BLOCK):
                continue

            jobs.append(
                {
                    "title": title,
                    "employer": employer,
                    "url": url,
                }
            )
        return jobs
