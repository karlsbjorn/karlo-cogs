import aiohttp
import os

import discord
from redbot.core import commands
from redbot.core import Config
from redbot.core.i18n import Translator, cog_i18n

from .wowpvp import Wowpvp
from .raiderio import Raiderio
from .wowtoken import Wowtoken
from .wowaudit import Wowaudit
from .raidbots import Raidbots

_ = Translator("WoWTools", __file__)


@cog_i18n(_)
class WoWTools(Wowpvp, Raiderio, Wowtoken, Wowaudit, Raidbots, commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069)
        default_global = {"region": "eu", "wowaudit_key": None}
        default_guild = {"auto_raidbots": True}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
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
        try:
            async with ctx.typing():
                if region not in regions:
                    raise ValueError(
                        _(
                            "That region does not exist.\nValid regions are: us, eu, kr, tw, cn"
                        )
                    )
                await self.config.region.set(region)
                await ctx.send(_("Region set succesfully."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @wowset.command()
    @commands.is_owner()
    async def wowaudit(self, ctx, key: str):
        """Set the key of your wowaudit spreadsheet."""
        try:
            async with ctx.typing():
                await self.config.wowaudit_key.set(key)
                await ctx.send(_("Wowaudit key set."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @wowset.command()
    @commands.admin()
    async def raidbots(self, ctx):
        """Toggle automatic response to a Raidbots simulation report."""
        try:
            if await self.config.guild(ctx.guild).auto_raidbots():
                await self.config.guild(ctx.guild).auto_raidbots.set(False)
                await ctx.send(_("Raidbots toggled off"))
            else:
                await self.config.guild(ctx.guild).auto_raidbots.set(True)
                await ctx.send(_("Raidbots toggled on"))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
