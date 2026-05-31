"""Utility helpers: URL normalisation, domain checks, ad-domain filtering."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse, urljoin

# ---------------------------------------------------------------------------
# Known ad / tracking / CDN domains to skip
# ---------------------------------------------------------------------------
AD_DOMAINS: frozenset[str] = frozenset(
    {
        "doubleclick.net",
        "googlesyndication.com",
        "googleadservices.com",
        "adservice.google.com",
        "ads.yahoo.com",
        "amazon-adsystem.com",
        "adsrvr.org",
        "adnxs.com",
        "outbrain.com",
        "taboola.com",
        "revcontent.com",
        "zergnet.com",
        "media.net",
        "adblade.com",
        "criteo.com",
        "rubiconproject.com",
        "openx.net",
        "pubmatic.com",
        "casalemedia.com",
        "contextweb.com",
        "sharethrough.com",
        "moatads.com",
        "scorecardresearch.com",
        "quantserve.com",
        "chartbeat.com",
    }
)

# Heuristic CSS class / id fragments that suggest ad/nav/footer content
# (used as a fallback inside extractor, not here)
AD_CLASS_PATTERNS: list[str] = [
    r"\bad\b",
    r"advertisement",
    r"sponsored",
    r"promo",
    r"banner",
    r"affiliate",
    r"sidebar",
    r"widget",
]

_AD_CLASS_RE = re.compile("|".join(AD_CLASS_PATTERNS), re.IGNORECASE)


def is_ad_class(class_str: str) -> bool:
    """Return True if the class/id string looks like an ad container."""
    return bool(_AD_CLASS_RE.search(class_str))


def normalise_url(url: str, base: str = "") -> str:
    """Resolve relative URLs and strip fragments / query strings."""
    if base:
        url = urljoin(base, url)
    parsed = urlparse(url)
    # Drop fragment; keep query (some sites use it for real content pages)
    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)


def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def same_domain(url: str, base_domain: str) -> bool:
    domain = get_domain(url)
    # Allow www. variants
    return domain == base_domain or domain == "www." + base_domain or "www." + domain == base_domain


def is_ad_url(url: str) -> bool:
    domain = get_domain(url)
    for ad in AD_DOMAINS:
        if domain == ad or domain.endswith("." + ad):
            return True
    return False


def url_to_filename(url: str) -> str:
    """Convert a URL into a safe filename stem."""
    parsed = urlparse(url)
    stem = (parsed.netloc + parsed.path).strip("/")
    stem = re.sub(r"[^\w\-]", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    return stem[:80] or "output"
