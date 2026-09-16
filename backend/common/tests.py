from django.test import RequestFactory, TestCase

from .pdf import absolute_media_url, soft_break


class AbsoluteMediaUrlTests(TestCase):
    """xhtml2pdf makes a real HTTP/file fetch for <img src> — a bare
    relative path like SchoolProfile.logo's "/mcss-logo.png" (a plain
    CharField, deliberately allowing either a Django-served /media/... path
    or an SPA-served static asset path) silently fails to load unless it's
    first made absolute against the current request's host."""

    def setUp(self):
        self.request = RequestFactory().get("/")  # Host: testserver — Django's test-default allowed host

    def test_relative_path_becomes_absolute_against_the_request_host(self):
        self.assertEqual(absolute_media_url(self.request, "/mcss-logo.png"), "http://testserver/mcss-logo.png")

    def test_media_path_becomes_absolute_too(self):
        self.assertEqual(absolute_media_url(self.request, "/media/avatars/x.jpg"), "http://testserver/media/avatars/x.jpg")

    def test_already_absolute_http_url_passes_through_unchanged(self):
        url = "https://cdn.example.com/logo.png"
        self.assertEqual(absolute_media_url(self.request, url), url)

    def test_data_uri_passes_through_unchanged(self):
        uri = "data:image/png;base64,AAAA"
        self.assertEqual(absolute_media_url(self.request, uri), uri)

    def test_empty_or_none_returns_empty_string(self):
        self.assertEqual(absolute_media_url(self.request, ""), "")
        self.assertEqual(absolute_media_url(self.request, None), "")


class SoftBreakTests(TestCase):
    """A long unbroken token (a payment reference — this app's own
    MCSS-<32-hex>-... format has no whitespace) runs straight off a fixed-
    width PDF table cell otherwise: confirmed live that xhtml2pdf's
    ReportLab-based text layout ignores CSS word-break/overflow-wrap on
    unbroken text, AND does not treat U+200B (zero-width space) as a break
    point either (it rendered as a visible tofu glyph and still didn't
    wrap) — a real space is the one thing confirmed to actually work."""

    def test_inserts_a_space_every_n_characters(self):
        self.assertEqual(soft_break("abcdefghij", every=4), "abcd efgh ij")

    def test_short_value_is_unchanged(self):
        self.assertEqual(soft_break("abc", every=14), "abc")

    def test_exact_multiple_has_no_trailing_space(self):
        self.assertEqual(soft_break("abcdefgh", every=4), "abcd efgh")

    def test_empty_or_none_passes_through(self):
        self.assertEqual(soft_break(""), "")
        self.assertIsNone(soft_break(None))

    def test_the_stored_value_round_trips_by_stripping_spaces_back_out(self):
        # Proves the transform is purely cosmetic/reversible — nothing about
        # the real reference identity is lost, only how it's laid out on
        # the printed page.
        original = "MCSS-49dc3925beb64d298d755758c516f1ed-e2etest1"
        self.assertEqual(soft_break(original).replace(" ", ""), original)
