import logging
from datetime import date, datetime, timedelta, UTC
from typing import List, Optional

from teamarr.core import (
    Event,
    EventStatus,
    LeagueMappingSource,
    SportsProvider,
    Team,
    TeamStats,
    Venue,
)
from teamarr.providers.euroleague.client import EuroleagueClient

logger = logging.getLogger(__name__)

class EuroleagueProvider(SportsProvider):
    def __init__(
        self,
        league_mapping_source: Optional[LeagueMappingSource] = None,
    ):
        self._league_mapping_source = league_mapping_source
        self._clients = {
            "E": EuroleagueClient(competition="E"),
            "U": EuroleagueClient(competition="U"),
        }

    @property
    def name(self) -> str:
        return "euroleague"

    def _get_competition_code(self, league: str) -> str:
        """Determines if it's Euroleague (E) or Eurocup (U)."""
        if self._league_mapping_source:
            mapping = self._league_mapping_source.get_mapping(league, self.name)
            if mapping and mapping.provider_league_id:
                # Assuming provider_league_id is 'E' or 'U'
                return mapping.provider_league_id
        
        if "eurocup" in league.lower():
            return "U"
        return "E"

    def _get_client(self, league: str) -> EuroleagueClient:
        code = self._get_competition_code(league)
        return self._clients.get(code, self._clients["E"])

    def _get_current_season(self) -> int:
        """Returns the start year of the current season."""
        today = date.today()
        # Seasons usually start in Sept/Oct. If we are in Jan-July, the season started last year.
        if today.month < 8:
            return today.year - 1
        return today.year

    def supports_league(self, league: str) -> bool:
        if self._league_mapping_source:
            return self._league_mapping_source.supports_league(league, self.name)
        return "euroleague" in league.lower() or "eurocup" in league.lower()

    def get_events(self, league: str, target_date: date) -> List[Event]:
        client = self._get_client(league)
        season = self._get_current_season()
        df = client.get_season_games(season)
        
        if df.empty:
            return []

        events = []
        for _, row in df.iterrows():
            try:
                event = self._parse_event_row(row, league, season)
                if event and event.start_time.date() == target_date:
                    events.append(event)
            except Exception as e:
                logger.warning(f"[Euroleague] Failed to parse event: {e}")
                continue
                
        return events

    def _parse_event_row(self, row: dict, league: str, season: int) -> Optional[Event]:
        try:
            game_code = row.get("gameCode")
            game_id = str(row.get("identifier") or row.get("gamecode")) # E2025_1
            
            client = self._get_client(league)
            
            # Teams - handles both formats
            home_code = row.get("homecode") or row.get("local.club.code")
            away_code = row.get("awaycode") or row.get("road.club.code")
            
            home_name = row.get("hometeam") or row.get("local.club.name", "")
            away_name = row.get("awayteam") or row.get("road.club.name", "")

            home_logo = row.get("local.club.images.crest") or client.get_team_logo(home_code, season)
            away_logo = row.get("road.club.images.crest") or client.get_team_logo(away_code, season)
            
            home_team = Team(
                id=home_code,
                provider=self.name,
                name=home_name,
                short_name=home_code,
                abbreviation=home_code,
                league=league,
                sport="basketball",
                logo_url=home_logo
            )
            
            away_team = Team(
                id=away_code,
                provider=self.name,
                name=away_name,
                short_name=away_code,
                abbreviation=away_code,
                league=league,
                sport="basketball",
                logo_url=away_logo
            )
            
            # Start Time - handles multiple formats
            start_time = None
            utc_date_str = row.get("utcDate") # 2026-02-12T17:30:00Z
            date_str = row.get("date") # 2026-02-12T18:30:00 OR Sep 30, 2025
            time_str = row.get("time", "00:00")
            
            if utc_date_str:
                try:
                    # Remove Z and replace with UTC offset
                    cleaned_utc = str(utc_date_str).replace("Z", "+00:00")
                    start_time = datetime.fromisoformat(cleaned_utc)
                except: pass
                
            if not start_time and date_str:
                if "T" in str(date_str):
                    try:
                        start_time = datetime.fromisoformat(str(date_str)).replace(tzinfo=UTC)
                    except: pass
                else:
                    try:
                        dt_str = f"{date_str} {time_str}"
                        start_time = datetime.strptime(dt_str, "%b %d, %Y %H:%M").replace(tzinfo=UTC)
                    except: pass
            
            if not start_time:
                return None

            # Status
            played = row.get("played", False)
            state = "final" if played else "scheduled"
            
            # Scores
            home_score = row.get("homescore") or row.get("local.score")
            away_score = row.get("awayscore") or row.get("road.score")
            
            return Event(
                id=game_id,
                provider=self.name,
                name=f"{away_team.name} at {home_team.name}",
                short_name=f"{away_code} @ {home_code}",
                start_time=start_time,
                home_team=home_team,
                away_team=away_team,
                status=EventStatus(state=state),
                league=league,
                sport="basketball",
                home_score=int(home_score) if played and home_score is not None else None,
                away_score=int(away_score) if played and away_score is not None else None,
                season_year=season
            )
        except Exception as e:
            logger.error(f"[Euroleague] Error parsing event row: {e}")
            return None

    def get_team_schedule(
        self,
        team_id: str,
        league: str,
        days_ahead: int = 14,
    ) -> List[Event]:
        logger.debug(f"[Euroleague] Fetching schedule for team {team_id} in {league}")
        client = self._get_client(league)
        season = self._get_current_season()
        df = client.get_season_games(season)
        
        if df.empty:
            return []

        events = []
        now = datetime.now(UTC)
        end_date = now + timedelta(days=days_ahead)

        for _, row in df.iterrows():
            home_code = row.get("homecode") or row.get("local.club.code")
            away_code = row.get("awaycode") or row.get("road.club.code")
            
            if str(home_code) == str(team_id) or str(away_code) == str(team_id):
                event = self._parse_event_row(row, league, season)
                if event:
                    # Include past games and upcoming within days_ahead
                    if event.start_time <= end_date:
                        events.append(event)
        
        events.sort(key=lambda e: e.start_time)
        return events

    def get_team(self, team_id: str, league: str) -> Optional[Team]:
        client = self._get_client(league)
        season = self._get_current_season()
        teams_df = client.get_teams(season)
        
        if teams_df.empty:
            return None
            
        team_row = None
        for _, row in teams_df.iterrows():
            if str(row.get("team.code")) == str(team_id):
                team_row = row
                break
        
        if team_row is not None:
            return Team(
                id=team_id,
                provider=self.name,
                name=team_row.get("team.name", ""),
                short_name=team_id,
                abbreviation=team_row.get("team.tvCodes", team_id),
                league=league,
                sport="basketball",
                logo_url=team_row.get("team.imageUrl")
            )
        return None

    def get_event(self, event_id: str, league: str) -> Optional[Event]:
        # event_id is E2025_1 or similar
        try:
            parts = event_id.split("_")
            if len(parts) != 2:
                return None
            
            season = int(parts[0][1:])
            game_code_str = parts[1]
            
            # Try to find in season games first (more reliable for upcoming games)
            client = self._get_client(league)
            df = client.get_season_games(season)
            if not df.empty:
                # gameCode in DF matches the integer part of game_id
                match = df[df['gameCode'].astype(str) == game_code_str]
                if not match.empty:
                    return self._parse_event_row(match.iloc[0].to_dict(), league, season)

            # Fallback to single event lookup if not found in season list
            # (though get_season_games now fetches all rounds, so this is unlikely)
            game_code = int(game_code_str)
            details = client.get_game_details(season, game_code)
            
            if not details:
                return None
            
            # Legacy mapping for get_game_details (metadata API)
            home_code = details.get("CodeTeamA")
            away_code = details.get("CodeTeamB")
            
            home_team = Team(
                id=home_code,
                provider=self.name,
                name=details.get("TeamA", ""),
                short_name=home_code,
                abbreviation=home_code,
                league=league,
                sport="basketball",
                logo_url=client.get_team_logo(home_code, season)
            )
            
            away_team = Team(
                id=away_code,
                provider=self.name,
                name=details.get("TeamB", ""),
                short_name=away_code,
                abbreviation=away_code,
                league=league,
                sport="basketball",
                logo_url=client.get_team_logo(away_code, season)
            )
            
            date_str = details.get("Date") # 30/09/2025
            time_str = details.get("Hour", "00:00").strip()
            dt_str = f"{date_str} {time_str}"
            start_time = datetime.strptime(dt_str, "%d/%m/%Y %H:%M").replace(tzinfo=UTC)
            
            played = details.get("Live") == False and (details.get("ScoreA") or details.get("ScoreB"))
            state = "final" if played else "scheduled"
            
            return Event(
                id=event_id,
                provider=self.name,
                name=f"{away_team.name} at {home_team.name}",
                short_name=f"{away_code} @ {home_code}",
                start_time=start_time,
                home_team=home_team,
                away_team=away_team,
                status=EventStatus(state=state),
                league=league,
                sport="basketball",
                home_score=int(details.get("ScoreA")) if played else None,
                away_score=int(details.get("ScoreB")) if played else None,
                season_year=season,
                venue=Venue(name=details.get("Stadium", ""))
            )
        except Exception as e:
            logger.error(f"[Euroleague] Error fetching single event {event_id}: {e}")
            return None

    def get_league_teams(self, league: str) -> List[Team]:
        client = self._get_client(league)
        season = self._get_current_season()
        teams_df = client.get_teams(season)
        
        teams = []
        if not teams_df.empty:
            for _, row in teams_df.iterrows():
                team_id = row.get("team.code")
                if team_id:
                    teams.append(Team(
                        id=team_id,
                        provider=self.name,
                        name=row.get("team.name", ""),
                        short_name=team_id,
                        abbreviation=row.get("team.tvCodes", team_id),
                        league=league,
                        sport="basketball",
                        logo_url=row.get("team.imageUrl")
                    ))
        return teams

    def get_supported_leagues(self) -> List[str]:
        if not self._league_mapping_source:
            return []
        mappings = self._league_mapping_source.get_leagues_for_provider(self.name)
        return sorted(m.league_code for m in mappings)
