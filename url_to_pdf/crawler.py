"""BFS crawler with depth control, deduplication, and live progress."""

from __future__ import annotations

from collections import Counter, deque
from typing import Optional

from bs4 import BeautifulSoup

from .extractor import Page, fetch_and_extract, BrowserSession
from .utils import get_domain, normalise_url, is_ad_url, same_domain

# A link (or anchor text) that appears on more than this fraction of all crawled
# pages is treated as site-wide navigation and stripped from the "Links on this
# page" sections.  0.5 = present on 50 %+ of pages.
NAV_FREQUENCY_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Shallow estimate
# ---------------------------------------------------------------------------


def estimate_link_count(start_url: str, max_depth: int = 2) -> int:
    """Quick BFS to estimate total reachable pages (JS-rendered)."""
    domain = get_domain(start_url)
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    visited.add(start_url)

    session = BrowserSession(timeout=15.0)
    count = 0

    try:
        while queue:
            url, depth = queue.popleft()
            count += 1
            print(
                f"\r  Scanning depth {depth:2d} | pages found: {count:4d} | queue: {len(queue):4d}  ",
                end="",
                flush=True,
            )
            if depth >= max_depth:
                continue
            frame_htmls = session.get_page_data(url)
            if not frame_htmls:
                continue
            for html in frame_htmls:
                soup = BeautifulSoup(html, "lxml")
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
    finally:
        print()  # newline after progress
        session.close()

    return count


# ---------------------------------------------------------------------------
# Navigation-link detection
# ---------------------------------------------------------------------------


def _find_nav_links(pages: list[Page], threshold: float = NAV_FREQUENCY_THRESHOLD) -> set[str]:
    """Return URLs and anchor texts that appear on > threshold of all pages.

    These are site-wide navigation items (header/footer/sidebar links) that
    should not appear in the per-chapter link lists.  The approach is purely
    frequency-based so it works for any website, not just Bizzdesign.
    """
    if not pages:
        return set()

    total = len(pages)
    url_counts: Counter[str] = Counter()
    text_counts: Counter[str] = Counter()

    for page in pages:
        # Count each URL and display text once per page (not per occurrence)
        seen_urls: set[str] = set()
        seen_texts: set[str] = set()
        for link_url, link_text in page.child_links:
            if link_url not in seen_urls:
                url_counts[link_url] += 1
                seen_urls.add(link_url)
            text_lower = link_text.strip().lower()
            if text_lower and text_lower not in seen_texts and not text_lower.startswith("http"):
                text_counts[text_lower] += 1
                seen_texts.add(text_lower)

    cutoff = total * threshold
    nav: set[str] = set()
    for url, count in url_counts.items():
        if count >= cutoff:
            nav.add(url)
    for text, count in text_counts.items():
        if count >= cutoff:
            nav.add(text)

    if nav:
        print(f"  Detected {len(nav)} site-wide navigation items (appear on ≥{threshold:.0%} of pages) — filtering from link lists.")

    return nav


def _strip_nav_links(pages: list[Page], nav: set[str]) -> None:
    """Remove navigation links from every page's child_links list in place."""
    if not nav:
        return
    for page in pages:
        page.child_links = [
            (url, text)
            for url, text in page.child_links
            if url not in nav and text.strip().lower() not in nav
        ]


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

    After crawling, automatically detects and strips site-wide navigation
    links (any link appearing on more than 50 % of pages).  This is
    site-agnostic and requires no hardcoded domain knowledge.

    *max_depth* of None means unlimited.
    """
    domain = get_domain(start_url)
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    visited.add(start_url)
    pages: list[Page] = []

    session = BrowserSession()

    try:
        while queue:
            url, depth = queue.popleft()

            print(
                f"\r  Crawling depth {depth:2d} | pages found: {len(pages):4d} | queue: {len(queue):4d}  ",
                end="",
                flush=True,
            )

            page = fetch_and_extract(
                url,
                session=session,
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

            for child_url, _ in page.child_links:
                if child_url not in visited:
                    visited.add(child_url)
                    queue.append((child_url, depth + 1))
    finally:
        session.close()
        print()  # newline after progress

    # Post-crawl: detect and strip site-wide navigation links
    nav = _find_nav_links(pages)
    _strip_nav_links(pages, nav)

    return pages
