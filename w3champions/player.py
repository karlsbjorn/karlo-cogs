import urllib.parse
from typing import List

from pydantic import BaseModel

from w3champions.mode import W3ChampionsMode
from w3champions.race import Race


class RaceStats(BaseModel):
    race: Race
    wins: int
    losses: int
    games: int
    winrate: float

    def to_row(self):
        return [
            self.race.name,
            self.wins,
            self.losses,
            f"{round(self.winrate * 100, 1)}%",
        ]


class ModeStats(BaseModel):
    gamemode: W3ChampionsMode
    race: Race | None
    mmr: int
    quantile: float
    wins: int
    losses: int
    games: int
    winrate: float

    def to_row(self):
        return [
            self.gamemode.name,
            self.wins,
            self.losses,
            f"{round(self.winrate * 100, 1)}%",
            self.mmr,
        ]


class OngoingMatch(BaseModel):
    map_name: str


class W3ChampionsPlayer(BaseModel):
    name: str
    location: str
    profile_picture_url: str
    total_games: int
    total_wins: int
    stats_by_race: List[RaceStats]
    stats_by_mode: List[ModeStats]
    ongoing_match: OngoingMatch | None

    def get_player_url(self) -> str:
        return urllib.parse.quote(f"https://w3champions.com/player/{self.name}", safe=":/")
