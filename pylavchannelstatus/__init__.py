from pylav.extension.red.utils.required_methods import pylav_auto_setup
from redbot.core.utils import get_end_user_data_statement

from .pylav_channel_status import PyLavChannelStatus

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot):
    await pylav_auto_setup(bot, PyLavChannelStatus)
