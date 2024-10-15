from dataclasses import dataclass
from enum import Enum


class ModeType(Enum):
    MELEE = 1
    NON_MELEE = 2


@dataclass
class W3ChampionsMode:
    id: int
    name: str
    type: ModeType
