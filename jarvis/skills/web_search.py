import webbrowser
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from jarvis.skills.base import BaseSkill, Tool

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/2.0"}


def _clean_ddg_link(href: str) -> str:
    # DuckDuckGo wraps result links as //duckduckgo.com/l/?uddg=<real url>
    if "uddg=" in href:
        return unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
    return href


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Search the web, read web pages, and open URLs in the browser"
    tools = [
        Tool(
            name="search",
            description="Search the web and return the top results (title, URL, snippet)",
            parameters={"query": {"type": "string", "description": "Search query"}},
            required=["query"],
        ),
        Tool(
            name="read_page",
            description="Fetch a web page and return its main text (first ~6000 characters)",
            parameters={"url": {"type": "string", "description": "Page URL"}},
            required=["url"],
        ),
        Tool(
            name="open_url",
            description="Open a URL in the user's default web browser",
            parameters={"url": {"type": "string", "description": "URL to open"}},
            required=["url"],
        ),
        Tool(
            name="open_search",
            description="Open a Google search for the query in the user's browser",
            parameters={"query": {"type": "string", "description": "Search query"}},
            required=["query"],
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "search":
            return self._search(args["query"])
        if action == "read_page":
            return self._read_page(args["url"])
        if action == "open_url":
            webbrowser.open(args["url"])
            return f"Opened {args['url']} in the browser."
        if action == "open_search":
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(args['query'])}")
            return f"Opened a Google search for '{args['query']}'."
        raise ValueError(f"Unknown action: {action}")

    def _search(self, query: str) -> str:
        try:
            resp = requests.post(
                "https://html.duckduckgo.com/html/", data={"q": query}, headers=HEADERS, timeout=15
            )
            resp.raise_for_status()
        except Exception as e:
            return f"Search failed: {e}"
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for block in soup.select(".result"):
            link = block.select_one(".result__a")
            if not link:
                continue
            snippet = block.select_one(".result__snippet")
            results.append(
                f"{len(results) + 1}. {link.get_text(strip=True)}\n"
                f"   {_clean_ddg_link(link.get('href', ''))}\n"
                f"   {snippet.get_text(' ', strip=True) if snippet else ''}"
            )
            if len(results) == 6:
                break
        return "\n".join(results) if results else f"No results found for '{query}'."

    def _read_page(self, url: str) -> str:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            return f"Could not fetch {url}: {e}"
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
            tag.decompose()
        root = soup.find("article") or soup.find("main") or soup.body or soup
        text = " ".join(root.get_text(" ", strip=True).split())
        return text[:6000] or "(no readable text)"
