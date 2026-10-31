"""Country-name translation tests (fork customization).

COUNTRY_TRANSLATIONS (matching direction, ES/PT→EN) is derived by inverting
ENGLISH_TO_SPANISH_COUNTRIES (display direction, EN→ES). These tests pin the
derivation invariants, the word-boundary replacement in
apply_city_translations, and the phrase-over-substring ordering.
"""

from unidecode import unidecode

from teamarr.consumers.matching.normalizer import (
    apply_city_translations,
    normalize_stream,
)
from teamarr.utilities.constants import (
    COUNTRY_TRANSLATIONS,
    ENGLISH_TO_SPANISH_COUNTRIES,
)


class TestDerivedDictionary:
    """COUNTRY_TRANSLATIONS must stay in lockstep with the display dict."""

    def test_every_display_entry_has_matching_inverse(self):
        for english, spanish in ENGLISH_TO_SPANISH_COUNTRIES.items():
            key = unidecode(spanish).lower()
            if key == english.lower():
                continue  # identity mappings are intentionally dropped
            assert COUNTRY_TRANSLATIONS[key] == english.lower(), (
                f"display entry {english!r}→{spanish!r} missing from matching dict"
            )

    def test_no_identity_mappings(self):
        assert all(k != v for k, v in COUNTRY_TRANSLATIONS.items())

    def test_longest_key_first_ordering(self):
        keys = list(COUNTRY_TRANSLATIONS)
        assert keys == sorted(keys, key=len, reverse=True)

    def test_colloquial_and_portuguese_variants_present(self):
        assert COUNTRY_TRANSLATIONS["holanda"] == "netherlands"
        assert COUNTRY_TRANSLATIONS["arabia saudita"] == "saudi arabia"
        assert COUNTRY_TRANSLATIONS["alemanha"] == "germany"
        assert COUNTRY_TRANSLATIONS["japao"] == "japan"
        assert COUNTRY_TRANSLATIONS["pais de gales"] == "wales"

    def test_previously_missing_countries_now_covered(self):
        """Countries the old hand-written dict lacked and fuzzy can't rescue."""
        assert COUNTRY_TRANSLATIONS["costa de marfil"] == "ivory coast"
        assert COUNTRY_TRANSLATIONS["emiratos arabes unidos"] == "united arab emirates"
        assert COUNTRY_TRANSLATIONS["corea del norte"] == "north korea"
        assert COUNTRY_TRANSLATIONS["arabia saudi"] == "saudi arabia"
        assert COUNTRY_TRANSLATIONS["argelia"] == "algeria"
        assert COUNTRY_TRANSLATIONS["tailandia"] == "thailand"
        assert COUNTRY_TRANSLATIONS["filipinas"] == "philippines"

    def test_original_hand_written_entries_survive_derivation(self):
        for key, value in {
            "alemania": "germany",
            "brasil": "brazil",
            "marruecos": "morocco",
            "inglaterra": "england",
            "espana": "spain",
            "estados unidos": "united states",
            "republica checa": "czech republic",
            "nueva zelanda": "new zealand",
        }.items():
            assert COUNTRY_TRANSLATIONS[key] == value


class TestWordBoundaries:
    def test_country_inside_longer_word_is_untouched(self):
        # "japon" must not fire inside "japones", "gales" not inside "legales"
        assert apply_city_translations("en japones") == "en japones"
        assert apply_city_translations("clausulas legales") == "clausulas legales"

    def test_exact_word_still_translates(self):
        assert apply_city_translations("Japon vs Gales") == "japan vs wales"

    def test_phrase_wins_over_substring(self):
        # "irlanda del norte" must not degrade to "ireland del norte"
        assert apply_city_translations("Irlanda del Norte") == "northern ireland"
        assert (
            apply_city_translations("Corea del Norte - Corea del Sur")
            == "north korea - south korea"
        )

    def test_accented_input_translates_via_unidecode(self):
        assert apply_city_translations("Japón") == "japan"
        assert apply_city_translations("Túnez vs Argelia") == "tunisia vs algeria"


class TestEndToEnd:
    def test_multiword_countries_normalize_in_pipeline(self):
        normalized = normalize_stream(
            "Costa de Marfil vs Emiratos Arabes Unidos"
        ).normalized.lower()
        assert "ivory coast" in normalized
        assert "united arab emirates" in normalized
