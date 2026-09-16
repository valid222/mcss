"""Shared helpers for the app's xhtml2pdf-rendered documents (report card,
payment receipt, ...)."""


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
