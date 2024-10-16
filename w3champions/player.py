from dataclasses import dataclass
from typing import List

from w3champions.mode import W3ChampionsMode
from w3champions.race import Race


@dataclass
class RaceStats:
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


@dataclass
class ModeStats:
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


@dataclass
class W3ChampionsPlayer:
    name: str
    profile_picture_url: str
    total_games: int
    total_wins: int
    stats_by_race: List[RaceStats]
    stats_by_mode: List[ModeStats]
