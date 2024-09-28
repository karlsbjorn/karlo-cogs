import datetime
import logging
from typing import Literal, Optional
from raiderio_async import RaiderIO

import aiohttp
import discord
from aiolimiter import AsyncLimiter
from aiowowapi import WowApi
from discord.ext import tasks
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild
from redbot.core.utils.chat_formatting import humanize_list

from wowtools.user_installable.cvardocs import CVar, CVarDocs

from .auctionhouse import AuctionHouse
from .guildmanage import GuildManage
from .on_message import OnMessage
from .pvp import PvP
from .raiderio import Raiderio
from .scoreboard import Scoreboard
from .token import Token
from .user_installable.auctionhouse import UserInstallableAuctionHouse
from .user_installable.raiderio import UserInstallableRaiderio

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)


@cog_i18n(_)
class WoWTools(
    PvP,
    Raiderio,
    Token,
    GuildManage,
    AuctionHouse,
    Scoreboard,
    OnMessage,
    CVarDocs,
    UserInstallableAuctionHouse,
    UserInstallableRaiderio,
    commands.Cog,
):
    """Interact with various World of Warcraft APIs"""

    def __init__(self, bot):
        self.on_message_cache: dict = {}
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
            "status_guild": [],
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
            "guild_log_welcome_channel": None,
            "guild_roster": {},
            "old_sb": None,
            "scoreboard_channel": None,
            "scoreboard_message": None,
            "scoreboard_blacklist": [],
            "sb_image": False,
            "on_message": False,
            "countdown_channel": None,
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
        self.blizzard: dict[str, WowApi] = {}
        self.cvar_cache: list[CVar] = []
        self.update_dungeon_scoreboard.start()
        self.guild_log.start()
        self.update_countdown_channels.start()
        self.update_bot_status.start()

    async def cog_load(self) -> None:
        blizzard_api = await self.bot.get_shared_api_tokens("blizzard")
        cid = blizzard_api.get("client_id")
        secret = blizzard_api.get("client_secret")
        if not cid or not secret:
            return
        self.blizzard["eu"] = WowApi(client_id=cid, client_secret=secret, client_region="eu")
        self.blizzard["us"] = WowApi(client_id=cid, client_secret=secret, client_region="us")
        self.blizzard["kr"] = WowApi(client_id=cid, client_secret=secret, client_region="kr")

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
        """Toggle the assistant cog integration."""
        enabled = await self.config.assistant_cog_integration()
        if enabled:
            await self.config.assistant_cog_integration.set(False)
            await ctx.send(_("Assistant cog integration disabled."))
        else:
            await self.config.assistant_cog_integration.set(True)
            await ctx.send(_("Assistant cog integration enabled."))

    @wowset.command(name="expansioncountdown", hidden=True)
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True, manage_channels=True)
    async def wowset_expansioncountdown(self, ctx: commands.Context):
        "Add or remove a locked channel to the channel list that will display the time until the next expansion releases."
        cd_channel_id = await self.config.guild(ctx.guild).countdown_channel()
        if cd_channel_id:
            cd_channel = ctx.guild.get_channel(cd_channel_id)
            if cd_channel:
                await cd_channel.delete(
                    reason=_(
                        "User with ID {cmd_author} requested deletion of countdown channel."
                    ).format(cmd_author=ctx.author.id)
                )
            await self.config.guild(ctx.guild).countdown_channel.clear()
            await ctx.send(_("Countdown channel removed"))
            return

        early_access_time = datetime.datetime(2024, 8, 22, 22, tzinfo=datetime.UTC)
        release_time = datetime.datetime(2024, 8, 26, 22, tzinfo=datetime.UTC)
        now = datetime.datetime.now(datetime.UTC)

        diff = early_access_time - now
        early_access = True
        if diff.total_seconds() < 0:
            diff = release_time - now
            early_access = False
        if diff.total_seconds() < 0:
            await ctx.send(_("The War Within has already released."))
            return

        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, __ = divmod(remainder, 60)
        if diff.days > 0:
            time_str = f"{days}d{hours}h{minutes}m"
        else:
            time_str = f"{hours}h {minutes}m"

        channel_name = (
            _("🔴War Within EA: {countdown}").format(countdown=time_str)
            if early_access
            else _("🟡War Within: {countdown}").format(countdown=time_str)
        )
        perms = {
            ctx.guild.default_role: discord.PermissionOverwrite(connect=False),
        }

        channel = await ctx.guild.create_voice_channel(
            channel_name, position=0, category=None, overwrites=perms
        )
        await self.config.guild(ctx.guild).countdown_channel.set(channel.id)
        await ctx.tick()

    @tasks.loop(minutes=6)
    async def update_countdown_channels(self):
        for guild in self.bot.guilds:
            if await self.bot.cog_disabled_in_guild(self, guild):
                continue
            countdown_channel_id: int = await self.config.guild(guild).countdown_channel()
            if countdown_channel_id is None:
                continue
            await set_contextual_locales_from_guild(self.bot, guild)

            countdown_channel = guild.get_channel(countdown_channel_id)
            if not countdown_channel:
                continue

            early_access_time = datetime.datetime(2024, 8, 22, 22, tzinfo=datetime.UTC)
            release_time = datetime.datetime(2024, 8, 26, 22, tzinfo=datetime.UTC)
            now = datetime.datetime.now(datetime.UTC)

            diff = early_access_time - now
            early_access = True
            if diff.total_seconds() < 0:
                diff = release_time - now
                early_access = False
            if diff.total_seconds() < 0:
                await countdown_channel.delete()
                await self.config.guild(guild).countdown_channel.clear()
                return

            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, __ = divmod(remainder, 60)
            if diff.days > 0:
                time_str = f"{days}d{hours}h{minutes}m"
            else:
                time_str = f"{hours}h {minutes}m"

            channel_name = (
                _("🔴War Within EA: {countdown}").format(countdown=time_str)
                if early_access
                else _("🟡War Within: {countdown}").format(countdown=time_str)
            )
            try:
                await countdown_channel.edit(name=channel_name)
            except Exception as e:
                # Probably rate limit stuff. Just ignore.
                log.debug("Exception in countdown channel editing. {}".format(e))

    @wowset.command(name="status", hidden=True)
    async def wowset_status(
        self,
        ctx: commands.Context,
        guild_name: str,
        realm: str,
        region,
        emoji: Optional[discord.Emoji] = None,
    ):
        status_guild = [
            guild_name.replace("-", " ").lower(),
            realm,
            region,
            emoji.id if emoji else None,
        ]
        await self.config.status_guild.set(status_guild)
        if await self.set_bot_status():
            await ctx.send(_("Status guild set."))
            return
        await ctx.send(_("Setting guild bot status failed."))

    async def set_bot_status(self) -> bool:
        try:
            guild, realm, region, emoji = await self.config.status_guild()
        except ValueError:
            return False

        async with RaiderIO() as rio:
            guild_data = await rio.get_guild_profile(
                region,
                realm,
                guild,
                fields=["raid_progression"],
            )
        try:
            guild: str = guild_data["name"]
            progress: str = guild_data["raid_progression"]["nerubar-palace"]["summary"]
        except KeyError:
            return False
        activity = discord.CustomActivity(
            name=f"{guild}: {progress}", emoji=self.bot.get_emoji(emoji)
        )
        await self.bot.change_presence(activity=activity)
        return True

    @tasks.loop(minutes=60)
    async def update_bot_status(self):
        if not self.set_bot_status():
            log.warning(f"Setting the bot's status failed.")

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.update_dungeon_scoreboard.stop()
        self.guild_log.stop()
        self.update_countdown_channels.stop()
        self.update_bot_status.stop()

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()
