from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase

from .pdf import absolute_media_url, soft_break, student_header


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


def _fake_image_response(content=b"\x89PNG-fake-bytes", content_type="image/png"):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.headers = {"Content-Type": content_type}
    resp.content = content
    return resp


class StudentHeaderCachingTests(TestCase):
    """common.pdf.student_header / _cached_image_data_uri — the fix for PDF
    generation being slow: without this, xhtml2pdf re-fetches the same
    logo over the network on every single request. Confirms a fetch only
    ever happens once per URL (cached after), and that a fetch failure
    falls back to handing xhtml2pdf the plain URL — exactly what happened
    before this caching existed — rather than dropping the image."""

    def setUp(self):
        cache.clear()
        self.request = RequestFactory().get("/")

    def test_a_successful_fetch_is_returned_as_a_data_uri(self):
        with patch("common.pdf.requests.get", return_value=_fake_image_response()) as mock_get:
            photo_url, logo_url = student_header(self.request, avatar="", logo="/mcss-logo.png")
        mock_get.assert_called_once()
        self.assertTrue(logo_url.startswith("data:image/png;base64,"))
        # No avatar -> the shared default placeholder, also a data: URI.
        self.assertTrue(photo_url.startswith("data:image/png;base64,"))

    def test_a_second_call_for_the_same_url_does_not_fetch_again(self):
        with patch("common.pdf.requests.get", return_value=_fake_image_response()) as mock_get:
            student_header(self.request, avatar="", logo="/mcss-logo.png")
            student_header(self.request, avatar="", logo="/mcss-logo.png")
        self.assertEqual(mock_get.call_count, 1)

    def test_a_failed_fetch_falls_back_to_the_plain_url_not_dropped(self):
        import requests as requests_lib

        with patch("common.pdf.requests.get", side_effect=requests_lib.ConnectionError("down")):
            photo_url, logo_url = student_header(self.request, avatar="/media/avatars/x.jpg", logo="/mcss-logo.png")
        self.assertEqual(logo_url, "http://testserver/mcss-logo.png")
        self.assertEqual(photo_url, "http://testserver/media/avatars/x.jpg")

    def test_a_failed_fetch_is_not_cached_so_the_next_request_retries(self):
        import requests as requests_lib

        with patch("common.pdf.requests.get", side_effect=requests_lib.ConnectionError("down")) as mock_get:
            student_header(self.request, avatar="", logo="/mcss-logo.png")
        self.assertEqual(mock_get.call_count, 1)

        with patch("common.pdf.requests.get", return_value=_fake_image_response()) as mock_get2:
            _photo_url, logo_url = student_header(self.request, avatar="", logo="/mcss-logo.png")
        mock_get2.assert_called_once()  # not skipped by a cached failure
        self.assertTrue(logo_url.startswith("data:image/png;base64,"))

    def test_no_logo_configured_stays_empty(self):
        with patch("common.pdf.requests.get") as mock_get:
            _photo_url, logo_url = student_header(self.request, avatar="", logo="")
        mock_get.assert_not_called()
        self.assertEqual(logo_url, "")
