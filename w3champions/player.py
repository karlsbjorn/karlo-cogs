from dataclasses import dataclass


@dataclass
class W3ChampionsPlayer:
    name: str
    profile_picture_url: str
    total_games: int
    total_wins: int
