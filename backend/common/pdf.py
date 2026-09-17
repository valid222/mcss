"""Shared helpers for the app's xhtml2pdf-rendered documents (report card,
payment receipt, ...). Every PDF that shows a school/student identity
header (logo + student photo) should build it through the functions here,
not re-derive its own — see student_header() below."""

import base64
import functools
import hashlib
import logging
from pathlib import Path

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

# How long a fetched image's base64 data stays cached. The main cost this
# saves is xhtml2pdf's OWN per-request image fetch — confirmed directly
# while testing this file's other fixes: with no caching, generating a
# report card makes a brand-new synchronous HTTP GET (with its own 3-attempt
# retry loop on failure) for the school logo on every single request, even
# though it's the exact same image every time. An hour is generous relative
# to how often a school actually changes its logo.
_IMAGE_CACHE_TTL = 3600


def absolute_media_url(request, path):
    """xhtml2pdf fetches <img src> values as real HTTP requests (or local
    file reads) — it has no browser-style "resolve relative to the current
    page" behavior, so a bare relative path like "/mcss-logo.png" or
    "/media/logos/x.png" (as stored on SchoolProfile.logo, deliberately a
    plain CharField so either shape is valid) silently fails to load. This
    makes it absolute against the current request's own host, which works
    whether the path is Django-served (/media/...) or served by the SPA
    build sitting behind the same nginx (everything in this app is one
    origin — see README/deploy notes), exactly like a browser would resolve
    it. Already-absolute URLs (S3, a CDN, ...) pass through unchanged."""
    if not path or path.startswith(("http://", "https://", "data:")):
        return path or ""
    return request.build_absolute_uri(path)


def soft_break(value, every=14):
    """Inserts a real space every `every` characters into a long unbroken
    token (a payment reference, mainly — this app's own MCSS-<32-hex>-...
    format, or whatever a gateway hands back, has no whitespace a renderer
    can wrap on). xhtml2pdf's text layout is ReportLab's Paragraph engine
    underneath, which does NOT implement CSS word-break/overflow-wrap on
    unbroken text — that's silently ignored — and, tried and confirmed
    NOT to work either, does not treat a zero-width space (U+200B) as a
    break point (it rendered as a visible tofu box AND still didn't wrap:
    the font has no glyph for it, and ReportLab's own line-breaker doesn't
    special-case it). A real space is the one thing guaranteed to work,
    since normal word-wrapping already relies on it everywhere else in
    these templates. It's a cosmetic change to a long reference's spacing
    on the printed page only — the stored value (what payments actually
    get looked up/reconciled by) is never touched."""
    if not value:
        return value
    return " ".join(value[i:i + every] for i in range(0, len(value), every))


@functools.lru_cache(maxsize=1)
def default_avatar_data_uri():
    """A generic person-silhouette placeholder for a student with no
    uploaded profile picture. Embedded as a base64 data: URI rather than a
    served URL — xhtml2pdf resolves image sources at PDF-render time with no
    guaranteed access to this server's own /static/ host, so a data URI is
    the one option that always works, in dev and prod alike, with no extra
    link_callback/static-resolution setup. Lives under apps/academics's own
    static/ dir (where it was first added) rather than being duplicated or
    moved — this function is the one shared way every PDF reaches it."""
    path = Path(__file__).resolve().parent.parent / "apps" / "academics" / "static" / "academics" / "default-avatar.png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _cached_image_data_uri(url):
    """Fetches `url` once and caches its base64 data: URI, so xhtml2pdf
    reads the bytes it already has instead of making its own (uncached,
    3-attempt-retry-on-failure) network request on every PDF generation for
    an image — a logo, near enough always — that hasn't changed since the
    last request. Returns None on any fetch problem (bad status, timeout,
    unreachable host) — deliberately NOT cached, and NOT the same as "no
    image": the caller falls back to handing xhtml2pdf the plain URL, same
    as it always did before this caching existed, rather than this making
    the logo silently disappear on a transient failure. The next request
    retries the fetch fresh rather than being stuck on a cached failure for
    the full TTL."""
    cache_key = "pdf:img:" + hashlib.sha256(url.encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/png").split(";")[0]
        encoded = base64.b64encode(resp.content).decode("ascii")
        data_uri = f"data:{content_type};base64,{encoded}"
    except requests.RequestException:
        logger.warning("Could not fetch PDF header image for caching: %s", url, exc_info=True)
        return None
    cache.set(cache_key, data_uri, _IMAGE_CACHE_TTL)
    return data_uri


def student_header(request, *, avatar, logo):
    """(photo_url, logo_url) for the identity header every student-facing
    PDF shares — school logo on the left, the student's own photo (or the
    default placeholder when they have none) on the right, per the
    school's chosen layout. One definition so report card, receipt, and
    any future document (transcript, certificate, ...) all resolve their
    header images identically instead of three near-duplicate call sites
    silently drifting apart.

    Both images are pre-fetched and cached as data: URIs here (see
    _cached_image_data_uri) rather than handed to xhtml2pdf as plain URLs —
    that's the fix for PDF generation being slow: without this, xhtml2pdf
    fetches the same logo over the network on every single request. If that
    fetch fails, this falls back to the plain URL (letting xhtml2pdf make
    its own attempt, exactly like before this caching existed) rather than
    dropping the image — a cache/fetch problem should never be worse than
    the pre-caching behavior."""
    avatar_url = absolute_media_url(request, avatar)
    photo_url = (avatar_url and _cached_image_data_uri(avatar_url)) or avatar_url or default_avatar_data_uri()
    logo_url = absolute_media_url(request, logo)
    if logo_url:
        logo_url = _cached_image_data_uri(logo_url) or logo_url
    return photo_url, logo_url
