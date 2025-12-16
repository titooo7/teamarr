"""Streak-related template variables.

Variables for winning/losing streaks, recent records, etc.
"""

from teamarr.templates.context import GameContext, TemplateContext
from teamarr.templates.variables.registry import (
    Category,
    SuffixRules,
    register_variable,
)


@register_variable(
    name="streak",
    category=Category.STREAKS,
    suffix_rules=SuffixRules.BASE_ONLY,
    description="Team's current streak (e.g., 'W3' or 'L2')",
)
def extract_streak(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    if ctx.team_stats and ctx.team_stats.streak:
        return ctx.team_stats.streak
    return ""


@register_variable(
    name="streak_raw",
    category=Category.STREAKS,
    suffix_rules=SuffixRules.BASE_ONLY,
    description="Team's streak as signed integer (positive=wins, negative=losses)",
)
def extract_streak_raw(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    if ctx.team_stats:
        return str(ctx.team_stats.streak_count)
    return "0"


@register_variable(
    name="home_team_streak",
    category=Category.STREAKS,
    suffix_rules=SuffixRules.ALL,
    description="Home team's current streak for this game",
)
def extract_home_team_streak(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    if not game_ctx or not game_ctx.event:
        return ""
    event = game_ctx.event
    is_home = event.home_team.id == ctx.team_config.team_id
    if is_home and ctx.team_stats and ctx.team_stats.streak:
        return ctx.team_stats.streak
    elif not is_home and game_ctx.opponent_stats and game_ctx.opponent_stats.streak:
        return game_ctx.opponent_stats.streak
    return ""


@register_variable(
    name="away_team_streak",
    category=Category.STREAKS,
    suffix_rules=SuffixRules.ALL,
    description="Away team's current streak for this game",
)
def extract_away_team_streak(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    if not game_ctx or not game_ctx.event:
        return ""
    event = game_ctx.event
    is_home = event.home_team.id == ctx.team_config.team_id
    if not is_home and ctx.team_stats and ctx.team_stats.streak:
        return ctx.team_stats.streak
    elif is_home and game_ctx.opponent_stats and game_ctx.opponent_stats.streak:
        return game_ctx.opponent_stats.streak
    return ""
