
from pydantic import BaseModel


class W3ChampionsLeague(BaseModel):
    division: int
    id: int
    name: str
