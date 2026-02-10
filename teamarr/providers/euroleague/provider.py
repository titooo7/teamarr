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
        # Filter games by date
        # Date format in df is "Sep 30, 2025"
        for _, row in df.iterrows():
            try:
                game_date_str = row.get("date")
                if not game_date_str:
                    continue
                
                game_date = datetime.strptime(game_date_str, "%b %d, %Y").date()
                if game_date == target_date:
                    event = self._parse_event_row(row, league, season)
                    if event:
                        events.append(event)
            except Exception as e:
                logger.warning(f"[Euroleague] Failed to parse game date {game_date_str}: {e}")
                continue
                
        return events

    def _parse_event_row(self, row: dict, league: str, season: int) -> Optional[Event]:
        try:
            game_code = int(row.get("gameCode"))
            game_id = str(row.get("gamecode")) # E2025_1
            
            client = self._get_client(league)
            
            # Teams
            home_code = row.get("homecode")
            away_code = row.get("awaycode")
            
            home_team = Team(
                id=home_code,
                provider=self.name,
                name=row.get("hometeam", ""),
                short_name=home_code,
                abbreviation=home_code,
                league=league,
                sport="basketball",
                logo_url=client.get_team_logo(home_code, season)
            )
            
            away_team = Team(
                id=away_code,
                provider=self.name,
                name=row.get("awayteam", ""),
                short_name=away_code,
                abbreviation=away_code,
                league=league,
                sport="basketball",
                logo_url=client.get_team_logo(away_code, season)
            )
            
            # Start Time
            date_str = row.get("date")
            time_str = row.get("time", "00:00")
            # "Sep 30, 2025 19:45"
            dt_str = f"{date_str} {time_str}"
            start_time = datetime.strptime(dt_str, "%b %d, %Y %H:%M")
            # Euroleague times are usually Central European Time (CET/CEST)
            # Use UTC for core Event to match Teamarr conventions.
            start_time = start_time.replace(tzinfo=UTC)

            # Status
            played = row.get("played", False)
            state = "final" if played else "scheduled"
            
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
                home_score=int(row.get("homescore")) if played else None,
                away_score=int(row.get("awayscore")) if played else None,
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
        client = self._get_client(league)
        season = self._get_current_season()
        df = client.get_season_games(season)
        
        if df.empty:
            return []

        events = []
        now = datetime.now(UTC)
        end_date = now + timedelta(days=days_ahead)

        for _, row in df.iterrows():
            if str(row.get("homecode")) == str(team_id) or str(row.get("awaycode")) == str(team_id):
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
        # event_id is E2025_1
        try:
            parts = event_id.split("_")
            if len(parts) != 2:
                return None
            
            season = int(parts[0][1:]) # remove 'E' or 'U'
            game_code = int(parts[1])
            
            client = self._get_client(league)
            details = client.get_game_details(season, game_code)
            
            if not details:
                return None
            
            # Map details to Event
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
            start_time = datetime.strptime(dt_str, "%d/%m/%Y %H:%M")
            start_time = start_time.replace(tzinfo=UTC)
            
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
