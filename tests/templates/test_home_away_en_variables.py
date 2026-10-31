"""{home_team_en}/{away_team_en} variables (fork customization #14).

Customization #7 translates {home_team}/{away_team} to Spanish for display
(national teams only — clubs pass through unchanged). Upstream #484
(v2.12.3) then built the starter templates' art/logo URLs from
{home_team|pascal}, which reads the now-translated variable — national-team
art URLs started resolving "Espana"/"Belgica" instead of "Spain"/"Belgium"
and falling back to generic art (see CUSTOMIZATIONS.md #13).

{home_team_en}/{away_team_en} are fork-owned escape hatches: same positional
extraction, no translation, for building URLs/keys that must stay in
English. This test proves they exist, resolve independently of the
display translation, and (being new fork names) can never collide with an
upstream variable.
"""

from datetime import UTC, datetime

from teamarr.core.types import Event, EventStatus, Team
from teamarr.templates.context import GameContext
from teamarr.templates.variables.home_away import (
    extract_away_team,
    extract_away_team_en,
    extract_home_team,
    extract_home_team_en,
)


def _team(name, abbrev):
    return Team(
        id=name, provider="espn", name=name, short_name=name,
        abbreviation=abbrev, league="fifa.world", sport="soccer",
    )


def _game_ctx(home: Team, away: Team) -> GameContext:
    event = Event(
        id="e1", provider="espn", name=f"{away.name} at {home.name}",
        short_name=f"{away.abbreviation} @ {home.abbreviation}",
        start_time=datetime.now(UTC), home_team=home, away_team=away,
        status=EventStatus(state="pre"), league="fifa.world", sport="soccer",
    )
    return GameContext(event=event)


class TestNationalTeamDiverges:
    """{home_team}/{away_team} translate; {home_team_en}/{away_team_en} don't."""

    def test_home_team_en_stays_english(self):
        game_ctx = _game_ctx(home=_team("Spain", "ESP"), away=_team("Belgium", "BEL"))
        assert extract_home_team(None, game_ctx) == "España"
        assert extract_home_team_en(None, game_ctx) == "Spain"

    def test_away_team_en_stays_english(self):
        game_ctx = _game_ctx(home=_team("Spain", "ESP"), away=_team("Belgium", "BEL"))
        assert extract_away_team(None, game_ctx) == "Bélgica"
        assert extract_away_team_en(None, game_ctx) == "Belgium"


class TestClubsAgree:
    """Clubs are never translated, so the two forms agree."""

    def test_home_team_en_matches_home_team_for_clubs(self):
        game_ctx = _game_ctx(
            home=_team("Real Madrid", "RMA"), away=_team("Detroit Lions", "DET")
        )
        assert extract_home_team(None, game_ctx) == extract_home_team_en(None, game_ctx)
        assert extract_home_team_en(None, game_ctx) == "Real Madrid"

    def test_away_team_en_matches_away_team_for_clubs(self):
        game_ctx = _game_ctx(
            home=_team("Real Madrid", "RMA"), away=_team("Detroit Lions", "DET")
        )
        assert extract_away_team(None, game_ctx) == extract_away_team_en(None, game_ctx)
        assert extract_away_team_en(None, game_ctx) == "Detroit Lions"


class TestNoGameContext:
    """Empty-safe like every other home/away extractor (registry sweep guarantee 1)."""

    def test_no_event_returns_empty(self):
        assert extract_home_team_en(None, None) == ""
        assert extract_away_team_en(None, None) == ""

    def test_event_less_game_context_returns_empty(self):
        empty_ctx = GameContext(event=None)
        assert extract_home_team_en(None, empty_ctx) == ""
        assert extract_away_team_en(None, empty_ctx) == ""
