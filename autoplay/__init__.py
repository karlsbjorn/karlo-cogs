import json
from pathlib import Path

from pylav.extension.red.utils.required_methods import pylav_auto_setup

from .autoplay import AutoPlay

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]


async def setup(bot):
    await pylav_auto_setup(bot, AutoPlay)
    await bot.add_cog(AutoPlay(bot))
