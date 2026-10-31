"""Tests for EPG program-data matching logic (teamarr-183.4 pure helpers).

Grounded in the live-probe findings: teams in sub_title, category gating with
classic-replay precedence, and graceful fallback when categories are absent.
"""

from teamarr.consumers.matching.classifier import StreamCategory, classify_stream
from teamarr.consumers.matching.epg_matcher import (
    EPGMatchPolicy,
    build_match_input,
    classify_program_policy,
    should_attempt,
)
from teamarr.dispatcharr.types import DispatcharrProgram


def _prog(title="MLB Baseball", sub_title="Chicago Cubs at St. Louis Cardinals", cats=()):
    return DispatcharrProgram.from_api(
        {
            "id": 1,
            "tvg_id": "espn",
            "title": title,
            "sub_title": sub_title,
            "custom_properties": {"categories": list(cats)} if cats else {},
        }
    )


# =============================================================== category gate


def test_sports_event_attempts():
    assert classify_program_policy(("Sports", "Sports event", "Baseball")) is EPGMatchPolicy.ATTEMPT


def test_sports_non_event_skips():
    p = ("Show", "Sports non-event", "Sports talk")
    assert classify_program_policy(p) is EPGMatchPolicy.SKIP_NON_EVENT


def test_classic_skips():
    assert classify_program_policy(("Sports", "Classic Sport Event")) is EPGMatchPolicy.SKIP_CLASSIC


def test_classic_takes_precedence_over_event():
    # Replays carry BOTH tags — classic must win (Super Bowl Classics, UFC Reloaded)
    cats = ("Sports", "Sports event", "Classic Sport Event", "Football")
    assert classify_program_policy(cats) is EPGMatchPolicy.SKIP_CLASSIC


def test_empty_categories_attempt_fallback():
    assert classify_program_policy(()) is EPGMatchPolicy.ATTEMPT


def test_unknown_categories_attempt():
    # Has categories, but none decisive → attempt, rely on team-match + window
    assert classify_program_policy(("Sports", "Baseball")) is EPGMatchPolicy.ATTEMPT


def test_category_matching_is_case_insensitive():
    assert classify_program_policy(("SPORTS NON-EVENT",)) is EPGMatchPolicy.SKIP_NON_EVENT


# =============================================================== input builder


def test_build_input_combines_title_and_subtitle():
    # title + sub_title joined with a pipe so the title is treated as a
    # league/sport hint and stripped, leaving a clean matchup for extraction.
    p = _prog("MLB Baseball", "Chicago Cubs at St. Louis Cardinals")
    assert build_match_input(p) == "MLB Baseball | Chicago Cubs at St. Louis Cardinals"


def test_build_input_generic_title_no_subtitle():
    p = _prog("NHL Hockey", None)
    assert build_match_input(p) == "NHL Hockey"


def test_build_input_strips_and_skips_empty():
    p = _prog("  Soccer  ", "")
    assert build_match_input(p) == "Soccer"


def test_build_input_empty_when_both_blank():
    p = _prog("", None)
    assert build_match_input(p) == ""


# ---- heterogeneous EPG formatting (epic crs.5) ----


def test_build_input_splits_inline_colon_matchup():
    # Xtream/Infinity style: whole matchup in the title with a " : " separator
    # and no sub_title — split so the league prefix becomes a strippable hint.
    p = _prog("MLB Baseball : New York Mets at Seattle Mariners", None)
    assert build_match_input(p) == "MLB Baseball | New York Mets at Seattle Mariners"


def test_build_input_strips_superscript_decorations():
    # Trailing superscript "Live"/"New" markers must not pollute the last team.
    p = _prog("MLB Baseball : New York Mets at Seattle Mariners ᴸᶦᵛᵉ", None)
    assert build_match_input(p) == "MLB Baseball | New York Mets at Seattle Mariners"
    p2 = _prog("WNBA Basketball", "Toronto Tempo at New York Liberty ᴺᵉʷ")
    assert build_match_input(p2) == "WNBA Basketball | Toronto Tempo at New York Liberty"


def test_build_input_inline_split_only_first_separator():
    # Only the first separator becomes the hint boundary; later ones are left.
    p = _prog("NBA : Game 1 : Knicks at Spurs", None)
    assert build_match_input(p) == "NBA | Game 1 : Knicks at Spurs"


def test_build_input_dash_separator_inline():
    p = _prog("Premier League — Arsenal vs Chelsea", None)
    assert build_match_input(p) == "Premier League | Arsenal vs Chelsea"


def test_build_input_ascii_dash_separator_inline():
    p = _prog("College Football - Missouri State at Texas A&M", None)
    match_input = build_match_input(p)
    assert match_input == "College Football | Missouri State at Texas A&M"

    classified = classify_stream(match_input, "team", None, None, None)
    assert classified.category is StreamCategory.TEAM_VS_TEAM
    assert classified.team1 == "Missouri State"
    assert classified.team2 == "Texas A&M"


def test_build_input_dash_matchup_is_not_split_between_teams():
    # Fork (v2.25.1 port): Movistar/DAZN write the matchup itself with a dash.
    # Splitting at that dash (upstream #728) put the two teams on either side
    # of the pipe and no pair was extracted (production, 2026-10-31).
    p = _prog("DIRECTO Jornada 9: Chelsea - Manchester United T26/27", None)
    assert build_match_input(p) == "DIRECTO Jornada 9: Chelsea - Manchester United T26/27"

    p = _prog("Real Madrid - Málaga", None)
    assert build_match_input(p) == "Real Madrid - Málaga"

    # A leading category dash still splits when a matchup follows it.
    p = _prog("Premier League - Chelsea - Man Utd", None)
    assert build_match_input(p) == "Premier League | Chelsea - Man Utd"


def test_build_input_no_split_when_subtitle_present():
    # A real title|sub_title split is authoritative; an in-title colon stays put.
    p = _prog("MLB Baseball: Special", "Cubs at Cardinals")
    assert build_match_input(p) == "MLB Baseball: Special | Cubs at Cardinals"


def test_build_input_strips_star_rating_suffix():
    """Fork customization #18 (2026-08-30): a guide-source star rating in
    sub_title ("2026 | TP | ★6.6/10") must not survive into the match input.

    "N.N/10" collides with normalizer.py's bare MM/DD date pattern — a
    fractional rating gets misread as a real date ("6/10" -> June 10),
    which is then trusted and silently kills an otherwise-correct team match
    on the real broadcast date. Root-caused via a live production incident
    (Real Madrid - Málaga, 2026-08-30): the teams scored 100/100 but the
    match was rejected as an 81-day date mismatch. Whole-number ratings
    (★6.0/10 -> "0/10") happen to form an invalid date and dodge the bug,
    which is why it went unnoticed until a fractional rating hit it.
    """
    p = _prog("DIRECTO Jornada 3: Real Madrid - Málaga T26/27 · LALIGA EA SPORTS",
               "2026 | TP | ★6.6/10")
    result = build_match_input(p)
    assert "★" not in result
    assert "/10" not in result
    assert "2026" in result  # the year and rating-category text are untouched
    assert "TP" in result


def test_build_input_star_rating_suffix_no_false_date():
    """End-to-end: the stripped rating must not survive to normalize_stream
    as a false extracted_date (the actual production failure mode)."""
    from teamarr.consumers.matching.normalizer import normalize_stream

    p = _prog("DIRECTO Jornada 3: Real Madrid - Málaga T26/27 · LALIGA EA SPORTS",
               "2026 | TP | ★6.6/10")
    normalized = normalize_stream(build_match_input(p))
    assert normalized.extracted_date is None

    # A whole-number rating ("★6.0/10") happened to dodge the bug via an
    # invalid "0/10" date — must keep behaving the same (no false positive
    # either way) now that the rating is stripped outright.
    p_whole = _prog("DIRECTO Jornada 3: Celta - Athletic T26/27 · LALIGA EA SPORTS",
                     "2026 | TP | ★6.0/10")
    normalized_whole = normalize_stream(build_match_input(p_whole))
    assert normalized_whole.extracted_date is None


def test_build_input_real_date_survives_rating_strip():
    # A genuine embedded date elsewhere in the string must still extract —
    # the rating strip must not over-match ordinary "N/N" text.
    from teamarr.consumers.matching.normalizer import normalize_stream

    p = _prog("MLB Baseball", "Chicago Cubs at St. Louis Cardinals 8/30 7:05 ET")
    normalized = normalize_stream(build_match_input(p))
    assert normalized.extracted_date is not None


def test_category_title_does_not_pollute_team_extraction():
    """Regression: a show/category title must not fold into the first team.

    Real linear EPG puts the category in title ("College Football") and the
    matchup in sub_title ("Missouri at Auburn"). Pipe-joining lets the
    classifier strip the title as a hint so teams extract cleanly — a plain
    space gave team1="College Football Missouri".
    """
    p = _prog(title="College Football", sub_title="Missouri at Auburn")
    classified = classify_stream(build_match_input(p), "team", None, None, None)
    assert classified.category is StreamCategory.TEAM_VS_TEAM
    assert classified.team1 == "Missouri"
    assert classified.team2 == "Auburn"


# =================================================================== combined


def test_should_attempt_true_for_real_game():
    assert should_attempt(_prog(cats=("Sports event",))) is True


def test_should_attempt_false_for_non_event():
    assert should_attempt(_prog(cats=("Sports non-event",))) is False


def test_should_attempt_false_for_classic():
    assert should_attempt(_prog(cats=("Sports event", "Classic Sport Event"))) is False


def test_should_attempt_true_for_generic_title_input():
    # "NHL Hockey" is a non-empty input → we attempt; TeamMatcher self-rejects
    # downstream (no teams). We don't duplicate team extraction here.
    assert should_attempt(_prog("NHL Hockey", None)) is True


def test_should_attempt_false_when_match_input_empty():
    # truly nothing to match on
    assert should_attempt(_prog("", None)) is False


# --- Title lexicon (#716): guides without categories name the replay in the title


def test_highlights_token_in_title_is_skip_classic_without_categories():
    # Sky's guide: no categories at all, the evidence is the trailing "Hlts".
    assert (
        classify_program_policy((), "PL: Brighton v Leeds United Hlts")
        is EPGMatchPolicy.SKIP_CLASSIC
    )


def test_replay_token_beats_a_sports_event_category():
    assert (
        classify_program_policy(("Sports event",), "Serie A | Juventus v AC Milan Replay")
        is EPGMatchPolicy.SKIP_CLASSIC
    )


def test_replay_words_are_whole_words_only():
    # "Highlighted" and "Replayed" are not in the lexicon; "Classic" is a real
    # event word ("Classic Boxing") and is deliberately not matched by title.
    assert classify_program_policy((), "Classic Boxing: Ali v Frazier") is EPGMatchPolicy.ATTEMPT
    highlighted = classify_program_policy((), "Highlighted Games: Cubs at Cardinals")
    assert highlighted is EPGMatchPolicy.ATTEMPT
    assert classify_program_policy((), "Live: Brighton v Leeds United") is EPGMatchPolicy.ATTEMPT


def test_should_attempt_reads_title_and_sub_title_for_replay_words():
    assert should_attempt(_prog(title="PL: Brighton v Leeds United Hlts", sub_title="")) is False
    assert should_attempt(_prog(title="Serie A", sub_title="Juventus v AC Milan (Replay)")) is False
    assert should_attempt(_prog(title="Serie A", sub_title="Juventus v AC Milan")) is True
