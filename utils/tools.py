import os
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"
SCRAPE_TIMEOUT = 10
MAX_SCRAPE_CHARS = 3000


def web_search(query: str, num_results: int = 5) -> list[dict]:
    """
    Search the web using Serper API.
    Returns a list of results with title, link, and snippet.
    """
    if not SERPER_API_KEY:
        print("  [WARN] SERPER_API_KEY not set, skipping web search")
        return []

    try:
        response = httpx.post(
            SERPER_URL,
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": num_results},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("organic", []):
            results.append({
                "title":   item.get("title", ""),
                "link":    item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return results

    except Exception as e:
        print(f"  [WARN] web_search failed: {e}")
        return []


def scrape_page(url: str) -> str:
    """
    Fetch a URL and return cleaned readable text.
    Strips nav, scripts, and boilerplate.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = httpx.get(url, headers=headers, timeout=SCRAPE_TIMEOUT, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "header", "footer",
                          "aside", "form", "iframe", "noscript"]):
            tag.decompose()

        # Get main content -- prefer article/main tags
        main = soup.find("article") or soup.find("main") or soup.find("body")
        if not main:
            return ""

        text = main.get_text(separator="\n", strip=True)

        # Collapse blank lines
        lines = [line for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)

        return cleaned[:MAX_SCRAPE_CHARS]

    except Exception as e:
        print(f"  [WARN] scrape_page({url}) failed: {e}")
        return ""


def format_search_results(results: list[dict]) -> str:
    """
    Format search results into a clean string for the agent prompt.
    """
    if not results:
        return "No search results available."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['snippet']}")
        lines.append(f"   Source: {r['link']}")
        lines.append("")

    return "\n".join(lines)