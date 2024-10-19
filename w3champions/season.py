from dataclasses import dataclass

from pydantic import BaseModel


class W3ChampionsSeason(BaseModel):
    id: int
