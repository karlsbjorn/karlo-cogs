import aiohttp

import discord
from redbot.core import commands
from redbot.core import Config
from redbot.core.i18n import Translator, cog_i18n

from .wowpvp import Wowpvp
from .raiderio import Raiderio
from .wowtoken import Wowtoken

_ = Translator("WoWTools", __file__)


@cog_i18n(_)
class WoWTools(Wowpvp, Raiderio, Wowtoken, commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069)
        default_global = {
            "region": "eu"
        }
        self.config.register_global(**default_global)
        self.session = aiohttp.ClientSession()

    @commands.group()
    async def wowset(self, ctx):
        """Change WoWTools settings."""
        pass

    @wowset.command()
    @commands.is_owner()
    async def region(self, ctx, region: str):
        """Set the region where characters and guilds will be searched for."""
        regions = ("us", "eu", "kr", "tw", "cn")
        async with ctx.typing():
            try:
                if region not in regions:
                    raise ValueError(_("That region does not exist.\nValid regions are: us, eu, kr, tw, cn"))
                await self.config.region.set(region)
                await ctx.send(_("Region set succesfully."))
            except Exception as e:
                await ctx.send(e)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
