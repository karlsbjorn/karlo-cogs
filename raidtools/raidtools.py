import logging

from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

from .event_create import EventView
from .slash_commands import SlashCommands

log = logging.getLogger("red.karlo-cogs.raidtools")
_ = Translator("WoWTools", __file__)


@cog_i18n(_)
class RaidTools(SlashCommands, commands.Cog):
    """Create and manage WoW raid events for your guild."""

    def __init__(self, bot: Red):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=87446677010550784)
        default_guild = {
            "events": {},
        }
        default_member = {
            "events": {},
        }
        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)
        # Persistent view
        self.bot.add_view(EventView(self.config))
