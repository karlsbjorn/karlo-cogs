import discord
from pydantic import BaseModel


class Alarm(BaseModel):
    id: int
    summary: str
    info: str
    status: str
    value_string: str
    last_status_change: int

    def get_status_color(self) -> discord.Colour:
        if self.status == "CRITICAL":
            return discord.Colour.red()
        if self.status == "WARNING":
            return discord.Colour.yellow()
        return discord.Colour.blurple()
