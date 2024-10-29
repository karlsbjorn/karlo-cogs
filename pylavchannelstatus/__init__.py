import json
from pathlib import Path

from pylav.extension.red.utils.required_methods import pylav_auto_setup

from .pylav_channel_status import PyLavChannelStatus

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]


async def setup(bot):
    await pylav_auto_setup(bot, PyLavChannelStatus)
