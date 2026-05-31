"""Page fetching and main-body text extraction."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
import trafilatura
from bs4 import BeautifulSoup

from .utils import normalise_url, is_ad_url, same_domain, get_domain, is_ad_class

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Page:
    url: str
    title: str
    text: str                        # main body text (plain)
    child_links: list[str] = field(default_factory=list)
    depth: int = 0


# ---------------------------------------------------------------------------
# HTTP client (shared, re-used across fetches)
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; url-to-pdf/1.0; "
        "+https://github.com/michael-glenn/url-to-pdf)"
    )
}


def _make_client(timeout: float = 15.0) -> httpx.Client:
    return httpx.Client(
        headers=_HEADERS,
        timeout=timeout,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=5),
    )


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def fetch_and_extract(
    url: str,
    client: httpx.Client,
    base_domain: str,
    include_images: bool = False,
    delay: float = 0.5,
) -> Optional[Page]:
    """Fetch *url*, extract main body text and same-domain child links.

    Returns None on HTTP error or if no meaningful content found.
    """
    try:
        time.sleep(delay)
        resp = client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type:
            return None
        html = resp.text
    except Exception:
        return None

    # --- Main body text via trafilatura ---
    text = trafilatura.extract(
        html,
        url=url,
        include_images=include_images,
        include_links=False,
        include_tables=True,
        no_fallback=False,
        favor_recall=True,
    ) or ""

    # --- Title ---
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    # --- Child links ---
    child_links: list[str] = []
    for a in soup.find_all("a", href=True):
        # Skip links inside obvious ad containers
        parents_classes = " ".join(
            " ".join(p.get("class", [])) + " " + (p.get("id") or "")
            for p in a.parents
            if hasattr(p, "get")
        )
        if is_ad_class(parents_classes):
            continue

        href = normalise_url(a["href"], base=url)
        if not href.startswith("http"):
            continue
        if is_ad_url(href):
            continue
        if not same_domain(href, base_domain):
            continue
        # Strip anchors already done in normalise_url; dedupe later
        child_links.append(href)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_links: list[str] = []
    for lnk in child_links:
        if lnk not in seen:
            seen.add(lnk)
            unique_links.append(lnk)

    return Page(url=url, title=title, text=text, child_links=unique_links)
