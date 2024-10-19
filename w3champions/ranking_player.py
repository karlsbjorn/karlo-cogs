
from pydantic import BaseModel


class W3ChampionsRankingPlayer(BaseModel):
    rank_number: int
    name: str
    location: str
    wins: int
    losses: int
    total_games: int
    winrate: float
    mmr: int

    def to_row(self):
        return [
            self.rank_number,
            f"{self.name} [{self.location}]",
            self.wins,
            self.losses,
            self.total_games,
            f"{round(self.winrate * 100, 1)}%",
            self.mmr,
        ]
