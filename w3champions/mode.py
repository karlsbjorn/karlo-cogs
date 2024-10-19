from enum import Enum

from pydantic import BaseModel


class ModeType(Enum):
    MELEE = 1
    NON_MELEE = 2


class W3ChampionsMode(BaseModel):
    id: int
    name: str
    type: ModeType
