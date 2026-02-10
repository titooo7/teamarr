import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
from euroleague_api.game_stats import GameStats
from euroleague_api.team_stats import TeamStats
from euroleague_api.game_metadata import GameMetadata

logger = logging.getLogger(__name__)

class EuroleagueClient:
    def __init__(self, competition: str = "E"):
        self.competition = competition
        self.game_stats = GameStats(competition=competition)
        self.team_stats = TeamStats(competition=competition)
        self.game_metadata = GameMetadata(competition=competition)
        self._logo_cache: Dict[str, str] = {}

    def get_season_games(self, season: int) -> pd.DataFrame:
        try:
            return self.game_stats.get_gamecodes_season(season)
        except Exception as e:
            logger.error(f"[Euroleague] Error fetching games for season {season}: {e}")
            return pd.DataFrame()

    def get_game_details(self, season: int, game_code: int) -> Optional[Dict[str, Any]]:
        try:
            df = self.game_metadata.get_game_metadata(season, game_code)
            if not df.empty:
                return df.iloc[0].to_dict()
            return None
        except Exception as e:
            logger.error(f"[Euroleague] Error fetching game details for {season}/{game_code}: {e}")
            return None

    def get_teams(self, season: int) -> pd.DataFrame:
        try:
            # We use traditional stats to get team info including logos
            return self.team_stats.get_team_stats_single_season("traditional", season)
        except Exception as e:
            logger.error(f"[Euroleague] Error fetching teams for season {season}: {e}")
            return pd.DataFrame()

    def get_team_logo(self, team_code: str, season: int) -> Optional[str]:
        if team_code in self._logo_cache:
            return self._logo_cache[team_code]
        
        teams_df = self.get_teams(season)
        if not teams_df.empty:
            for _, row in teams_df.iterrows():
                code = row.get("team.code")
                url = row.get("team.imageUrl")
                if code:
                    self._logo_cache[code] = url
        
        return self._logo_cache.get(team_code)
