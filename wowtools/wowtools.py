import logging
from typing import Literal

import aiohttp
import discord
from aiolimiter import AsyncLimiter
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import humanize_list

from .auctionhouse import AuctionHouse
from .guildmanage import GuildManage
from .on_message import OnMessage
from .pvp import PvP
from .raiderio import Raiderio
from .scoreboard import Scoreboard
from .token import Token

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)


@cog_i18n(_)
class WoWTools(
    PvP, Raiderio, Token, GuildManage, AuctionHouse, Scoreboard, OnMessage, commands.Cog
):
    """Interact with various World of Warcraft APIs"""

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=42069)
        default_global = {
            "wowaudit_key": None,
            "emotes": {
                "gold": None,
                "silver": None,
                "copper": None,
            },
            "assistant_cog_integration": False,
        }
        default_guild = {
            "region": None,
            "realm": None,
            "real_guild_name": None,
            "gmanage_guild": None,
            "gmanage_realm": None,
            "guild_rankstrings": {},
            "guild_rankroles": {},
            "guild_log_channel": None,
            "guild_roster": {},
            "old_sb": None,
            "scoreboard_channel": None,
            "scoreboard_message": None,
            "scoreboard_blacklist": [],
            "sb_image": False,
            "on_message": False,
        }
        default_user = {
            "wow_character_name": None,
            "wow_character_realm": None,
            "wow_character_region": None,
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)
        self.limiter = AsyncLimiter(100, time_period=1)
        self.session = aiohttp.ClientSession(headers={"User-Agent": "Red-DiscordBot/WoWToolsCog"})
        self.update_dungeon_scoreboard.start()
        self.guild_log.start()

    @commands.group()
    async def wowset(self, ctx):
        """Change WoWTools settings."""
        pass

    @wowset.command(name="region")
    @commands.admin()
    async def wowset_region(self, ctx: commands.Context, region: str):
        """Set the region where characters and guilds will be searched for."""
        regions = ("us", "eu", "kr", "cn")
        try:
            async with ctx.typing():
                if region not in regions:
                    raise ValueError(
                        _("That region does not exist.\nValid regions are: {regions}.").format(
                            regions=humanize_list(regions)
                        )
                    )
                await self.config.guild(ctx.guild).region.set(region)
            await ctx.send(_("Region set succesfully."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @wowset.command(name="realm")
    @commands.admin()
    async def wowset_realm(self, ctx: commands.Context, realm: str = None):
        """Set the realm of your guild."""
        try:
            async with ctx.typing():
                if realm is None:
                    await self.config.guild(ctx.guild).realm.clear()
                    await ctx.send(_("Realm cleared."))
                    return
                realm = realm.lower()
                await self.config.guild(ctx.guild).realm.set(realm)
            await ctx.send(_("Realm set."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @wowset.command(name="guild")
    @commands.admin()
    async def wowset_guild(self, ctx: commands.Context, guild_name: str = None):
        """(CASE SENSITIVE) Set the name of your guild."""
        try:
            async with ctx.typing():
                if guild_name is None:
                    await self.config.guild(ctx.guild).real_guild_name.clear()
                    await ctx.send(_("Guild name cleared."))
                    return
                await self.config.guild(ctx.guild).real_guild_name.set(guild_name)
            await ctx.send(_("Guild name set."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @wowset.command(name="blizzard")
    @commands.is_owner()
    async def wowset_blizzard(self, ctx: commands.Context):
        """Instructions for setting up the Blizzard API."""
        return await ctx.send(
            _(
                "Create a client on https://develop.battle.net/ and then type in "
                "`{prefix}set api blizzard client_id,whoops client_secret,whoops` "
                "filling in `whoops` with your client's ID and secret."
            ).format(prefix=ctx.prefix)
        )

    @wowset.command(name="emote")
    @commands.is_owner()
    async def wowset_emote(
        self, ctx: commands.Context, currency: str, emoji: discord.Emoji = None
    ):
        """Set the emotes used for gold, silver and copper."""
        currency = currency.lower()
        if currency not in ["gold", "silver", "copper"]:
            return await ctx.send(_("Invalid currency."))
        if emoji:
            await self.config.emotes.set_raw(currency, value=str(emoji))
            await ctx.send(
                _("{currency} emote set to {emoji}").format(currency=currency.title(), emoji=emoji)
            )
        else:
            await self.config.emotes.set_raw(currency, value=None)
            await ctx.send(_("{currency} emote removed.").format(currency=currency.title()))

    @wowset.command(name="images")
    @commands.admin()
    @commands.guild_only()
    async def wowset_images(self, ctx: commands.Context):
        """Toggle scoreboard images on or off."""
        enabled = await self.config.guild(ctx.guild).sb_image()
        if enabled:
            await self.config.guild(ctx.guild).sb_image.set(False)
            await ctx.send(_("Images disabled."))
        else:
            await self.config.guild(ctx.guild).sb_image.set(True)
            await ctx.send(_("Images enabled."))

    @wowset.group(name="character")
    async def wowset_character(self, ctx):
        """Character settings."""
        pass

    @wowset_character.command(name="name")
    async def wowset_character_name(self, ctx, character_name: str):
        """Set your character name."""
        await self.config.user(ctx.author).wow_character_name.set(character_name)
        await ctx.send(_("Character name set."))

    @wowset_character.command(name="realm")
    async def wowset_character_realm(self, ctx, realm_name: str):
        """Set your character's realm."""
        await self.config.user(ctx.author).wow_character_realm.set(realm_name)
        await ctx.send(_("Character realm set."))

    @wowset_character.command(name="region")
    async def wowset_character_region(self, ctx, region: str):
        """Set your character's region."""
        regions = ("us", "eu", "kr", "cn")
        if region.lower() not in regions:
            await ctx.send(
                _("That region does not exist.\nValid regions are: {regions}.").format(
                    regions=", ".join(regions)
                )
            )
            return
        await self.config.user(ctx.author).wow_character_region.set(region)
        await ctx.send(_("Character region set."))

    @wowset.command(name="onmessage")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def wowset_on_message(self, ctx: commands.Context):
        """Toggle the bot's ability to respond to messages when a supported spell/item name is mentioned."""
        enabled = await self.config.guild(ctx.guild).on_message()
        if enabled:
            await self.config.guild(ctx.guild).on_message.set(False)
            await ctx.send(_("On message disabled."))
        else:
            await self.config.guild(ctx.guild).on_message.set(True)
            await ctx.send(_("On message enabled."))

    @wowset.command(name="assintegration")
    @commands.is_owner()
    async def wowset_assintegration(self, ctx: commands.Context):
        enabled = await self.config.assistant_cog_integration()
        if enabled:
            await self.config.assistant_cog_integration.set(False)
            await ctx.send(_("Assistant cog integration disabled."))
        else:
            await self.config.assistant_cog_integration.set(True)
            await ctx.send(_("Assistant cog integration enabled."))

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.update_dungeon_scoreboard.stop()
        self.guild_log.stop()

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()
