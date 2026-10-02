import os

import httpx

# The three buckets from the spec: research -> Scholar, market -> News, else -> Google.
ENGINES = {
    "research": ("google_scholar", "organic_results"),
    "market": ("google_news", "news_results"),
    "general": ("google", "organic_results"),
}


def run_search(query: str, bucket: str, n: int = 5) -> list[dict]:
    engine, key = ENGINES.get(bucket, ENGINES["general"])
    r = httpx.get(
        "https://serpapi.com/search.json",
        params={"engine": engine, "q": query, "api_key": os.environ["SERPAPI_API_KEY"]},
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for item in r.json().get(key, [])[:n]:
        link = item.get("link")
        if not link:
            continue
        out.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": link,
        })
    return out
