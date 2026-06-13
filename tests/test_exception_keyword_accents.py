"""Tests for accent-insensitive exception keyword matching.

Verifies that stream names with un-accented Latin text (e.g. ``espanol``)
match keywords configured with accented terms (e.g. ``Español``), and that
the accent stripping is applied symmetrically to both sides so CJK / Hangul
terms still self-match.
"""

import pytest

from teamarr.database.channels.keywords import (
    _make_keyword_pattern,
    _strip_accents,
    check_exception_keyword,
)
from teamarr.database.exception_keywords import ExceptionKeyword


def _kw(label: str, terms: str, behavior: str = "consolidate") -> ExceptionKeyword:
    return ExceptionKeyword(label=label, match_terms=terms, behavior=behavior)


# =============================================================================
# _strip_accents helper
# =============================================================================


class TestStripAccents:
    def test_spanish_tilde(self):
        assert _strip_accents("español") == "espanol"

    def test_french_cedilla_circumflex(self):
        assert _strip_accents("français") == "francais"
        assert _strip_accents("être") == "etre"

    def test_portuguese(self):
        assert _strip_accents("português") == "portugues"

    def test_no_accents_unchanged(self):
        # _strip_accents removes diacritics only — it does NOT lowercase.
        assert _strip_accents("spanish") == "spanish"
        assert _strip_accents("(ESP)") == "(ESP)"

    def test_cjk_unchanged_chars(self):
        # CJK ideographs have no combining marks — they pass through unchanged.
        assert _strip_accents("日本語") == "日本語"
        assert _strip_accents("中文") == "中文"

    def test_already_ascii(self):
        assert _strip_accents("espanol") == "espanol"


# =============================================================================
# Accent-insensitive matching
# =============================================================================


class TestAccentInsensitiveMatching:
    """The FIFA WC bug: 'espanol' must match the 'Español' term."""

    def test_unaccented_stream_matches_accented_term(self):
        """Reproduces the reported bug: stream 'en espanol' matches 'Español'."""
        keywords = [
            _kw("Spanish", "Spanish, En Español, (ESP), Español"),
        ]
        stream = "FIFA WC 07: Brazil vs Morocco 6:00 pm EN espanol"
        label, behavior = check_exception_keyword(stream, keywords)
        assert label == "Spanish"
        assert behavior == "consolidate"

    def test_accented_stream_matches_accented_term(self):
        """Accented stream text still matches accented term (no regression)."""
        keywords = [_kw("Spanish", "Spanish, En Español, (ESP), Español")]
        stream = "Partido En Español Brazil vs Morocco"
        assert check_exception_keyword(stream, keywords) == ("Spanish", "consolidate")

    def test_portuguese_still_matches(self):
        """Portuguese already worked — confirm no regression."""
        keywords = [_kw("Portuguese", "Portuguese, (POR), Português")]
        stream = "FIFA WC 08: Brazil vs Morocco 6:00 pm EN portuguese"
        assert check_exception_keyword(stream, keywords) == ("Portuguese", "consolidate")

    def test_unaccented_portuguese_accented_term(self):
        """'portugues' (no accent) matches the 'Português' term."""
        keywords = [_kw("Portuguese", "Portuguese, (POR), Português")]
        stream = "Jogo em portugues Brazil vs Morocco"
        assert check_exception_keyword(stream, keywords) == ("Portuguese", "consolidate")

    def test_french_unaccented_matches(self):
        """'en francais' (no cedilla) matches the 'Français' term."""
        keywords = [_kw("French", "French, En Français, (FRA), Français")]
        stream = "Match en francais"
        assert check_exception_keyword(stream, keywords) == ("French", "consolidate")

    def test_cjk_term_self_matches(self):
        """Hangul/CJK terms still match identical stream text (symmetric transform)."""
        keywords = [_kw("Korean", "Korean, (KOR), 한국어")]
        stream = "Game Korean feed 한국어"
        assert check_exception_keyword(stream, keywords) == ("Korean", "consolidate")

    def test_no_false_positive_unrelated(self):
        """'espanol' must not match a non-Spanish keyword."""
        keywords = [
            _kw("French", "French, En Français, (FRA), Français"),
            _kw("German", "German, (GER), Deutsch"),
        ]
        stream = "FIFA WC 07: Brazil vs Morocco 6:00 pm EN espanol"
        assert check_exception_keyword(stream, keywords) == (None, None)


# =============================================================================
# Pattern construction
# =============================================================================


class TestMakeKeywordPattern:
    def test_accented_term_produces_ascii_pattern(self):
        """The built pattern uses the stripped form so it matches pre-stripped text.

        ``_make_keyword_pattern`` strips the term; the caller (``check_exception_keyword``)
        strips the stream text. Here we test against the pre-stripped stream to mirror
        the real call path — full end-to-end accent matching is covered in
        ``TestAccentInsensitiveMatching``.
        """
        pattern = _make_keyword_pattern("Español")
        import re

        # Pre-stripped stream text (what check_exception_keyword feeds in).
        assert re.search(pattern, "feed en espanol hd")

    def test_paren_term_boundary_unchanged(self):
        """Non-word terms like '(ESP)' keep their lookaround boundaries."""
        pattern = _make_keyword_pattern("(ESP)")
        assert pattern.startswith("(?<!\\w)")
        assert pattern.endswith("(?!\\w)")
