"""Display-side country translation tests (fork customization).

_translate_country_for_display converts ESPN's English country names to
Spanish in the {home_team}/{away_team} template variables — including youth
and women's national team suffixes — while leaving club names untouched.
"""

from teamarr.templates.variables.home_away import _translate_country_for_display


class TestExactCountryNames:
    def test_translates_countries(self):
        assert _translate_country_for_display("Spain") == "España"
        assert _translate_country_for_display("Saudi Arabia") == "Arabia Saudí"
        assert _translate_country_for_display("Ivory Coast") == "Costa de Marfil"

    def test_identity_countries_pass_through(self):
        assert _translate_country_for_display("Argentina") == "Argentina"

    def test_clubs_untouched(self):
        assert _translate_country_for_display("Real Madrid") == "Real Madrid"
        assert _translate_country_for_display("Detroit Lions") == "Detroit Lions"

    def test_empty_string(self):
        assert _translate_country_for_display("") == ""


class TestYouthAndWomenSuffixes:
    def test_u_suffixes(self):
        assert _translate_country_for_display("Spain U21") == "España U21"
        assert _translate_country_for_display("Mexico U-20") == "México U-20"
        assert _translate_country_for_display("Japan U23") == "Japón U23"

    def test_w_suffix(self):
        assert _translate_country_for_display("Spain W") == "España W"

    def test_suffix_on_non_country_untouched(self):
        # Base is not a country → no translation, suffix or not.
        assert (
            _translate_country_for_display("Golden State Warriors W")
            == "Golden State Warriors W"
        )
        assert _translate_country_for_display("Ajax U21") == "Ajax U21"

    def test_lowercase_w_is_not_a_suffix(self):
        assert _translate_country_for_display("Spain w") == "Spain w"

    def test_identity_country_with_suffix(self):
        assert _translate_country_for_display("Argentina U20") == "Argentina U20"
