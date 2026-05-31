"""BFS crawler with depth control, deduplication, and live progress."""

from __future__ import annotations

import sys
from collections import deque
from typing import Optional

import httpx

from .extractor import Page, fetch_and_extract, _make_client
from .utils import get_domain, normalise_url, is_ad_url, same_domain


# ---------------------------------------------------------------------------
# Shallow estimate
# ---------------------------------------------------------------------------


def estimate_link_count(start_url: str, max_depth: int = 2) -> int:
    """Quick BFS to estimate total reachable pages (no content extraction)."""
    domain = get_domain(start_url)
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    visited.add(start_url)

    client = _make_client(timeout=10.0)
    count = 0

    try:
        while queue:
            url, depth = queue.popleft()
            count += 1
            if depth >= max_depth:
                continue
            try:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = normalise_url(a["href"], base=url)
                    if not href.startswith("http"):
                        continue
                    if is_ad_url(href):
                        continue
                    if not same_domain(href, domain):
                        continue
                    if href not in visited:
                        visited.add(href)
                        queue.append((href, depth + 1))
            except Exception:
                continue
    finally:
        client.close()

    return count


# ---------------------------------------------------------------------------
# Main crawl
# ---------------------------------------------------------------------------


def crawl(
    start_url: str,
    max_depth: Optional[int],
    delay: float = 0.5,
    include_images: bool = False,
) -> list[Page]:
    """BFS crawl returning ordered list of Pages (root first).

    *max_depth* of None means unlimited.
    """
    domain = get_domain(start_url)
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    visited.add(start_url)
    pages: list[Page] = []

    client = _make_client()

    try:
        while queue:
            url, depth = queue.popleft()

            # Progress indicator
            print(
                f"\r  Crawling depth {depth:2d} | pages found: {len(pages):4d} | queue: {len(queue):4d}  ",
                end="",
                flush=True,
            )

            page = fetch_and_extract(
                url,
                client=client,
                base_domain=domain,
                include_images=include_images,
                delay=delay,
            )
            if page is None:
                continue
            page.depth = depth
            pages.append(page)

            if max_depth is not None and depth >= max_depth:
                continue

            for child_url in page.child_links:
                if child_url not in visited:
                    visited.add(child_url)
                    queue.append((child_url, depth + 1))
    finally:
        client.close()
        print()  # newline after progress

    return pages
