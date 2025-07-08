import datetime
import logging
from typing import Literal, Mapping, Optional

import aiohttp
import discord
from aiolimiter import AsyncLimiter
from aiowowapi import WowApi
from discord.ext import tasks
from raiderio_async import RaiderIO
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
        self.raiderio_api = RaiderIO()
        self.blizzard: dict[str, WowApi] = {}
        self.cvar_cache: list[CVar] = []
        self.roster_cache: dict[int, dict] = {}
        self.update_dungeon_scoreboard.start()
        log.info("Dungeon scoreboard updater started.")
        self.guild_log.start()
        log.info("Guild log updater started.")
        self.update_countdown_channels.start()
        log.info("Countdown channel updater started.")
        self.update_bot_status.start()
        log.info("Bot status updater started.")

        self.current_raid = "liberation-of-undermine"
        # For countdown channels
        self.early_access_time = (
            datetime.datetime(  # Expansion "early access", or patch release without raid/m+
                year=2025, month=8, day=5, hour=4, tzinfo=datetime.UTC
            )
        )
        self.release_time = (  # Full expansion release, or season release with raid/m+
            datetime.datetime(year=2025, month=8, day=12, hour=4, tzinfo=datetime.UTC)
        )

    async def cog_load(self) -> None:
        raiderio_api_key = await self.bot.get_shared_api_tokens("raiderio")
        self.raiderio_api = RaiderIO(api_key=raiderio_api_key.get("api_key"))
        await self.create_bnet_objs()

    async def create_bnet_objs(self):
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

    @commands.hybrid_group()
    async def serverset(self, ctx):
        """Change WoW guild-related settings"""
        pass

    @serverset.command(name="region")
    @commands.guild_only()
    @commands.admin()
    async def serverset_region(self, ctx: commands.GuildContext, region: str):
        """Set the region where characters and guilds will be searched for."""
        regions = ("us", "eu", "kr")
        try:
            async with ctx.typing():
                if region not in regions:
                    await ctx.send(
                        _("That region does not exist.\nValid regions are: {regions}.").format(
                            regions=humanize_list(regions),
                        ),
                        ephemeral=True,
                    )
                await self.config.guild(ctx.guild).region.set(region)
            await ctx.send(_("Region set succesfully."), ephemeral=True)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e), ephemeral=True)

    @serverset.command(name="realm")
    @commands.guild_only()
    @commands.admin()
    async def serverset_realm(self, ctx: commands.GuildContext, realm: str | None = None):
        """Set the realm of your guild."""
        try:
            async with ctx.typing():
                if not realm:
                    await self.config.guild(ctx.guild).realm.clear()
                    await ctx.send(_("Realm cleared."), ephemeral=True)
                    return
                realm = realm.lower()
                await self.config.guild(ctx.guild).realm.set(realm)
            await ctx.send(_("Realm set."), ephemeral=True)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e), ephemeral=True)

    @serverset.command(name="guild")
    @commands.guild_only()
    @commands.admin()
    async def serverset_guild(self, ctx: commands.GuildContext, guild_name: str | None = None):
        """Set the name of your guild."""
        try:
            async with ctx.typing():
                if guild_name is None:
                    await self.config.guild(ctx.guild).real_guild_name.clear()
                    await ctx.send(_("Guild name cleared."), ephemeral=True)
                    return
                guild_name = guild_name.replace("-", " ").title()
                await self.config.guild(ctx.guild).real_guild_name.set(guild_name)
            await ctx.send(_("Guild name set."), ephemeral=True)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e), ephemeral=True)

    @wowset.command(name="blizzard")
    @commands.is_owner()
    async def wowset_blizzard(self, ctx: commands.Context):
        """Instructions for setting up the Blizzard API."""
        await ctx.send(
            _(
                "Create a client on https://develop.battle.net/ and then type in "
                "`{prefix}set api blizzard client_id,whoops client_secret,whoops` "
                "filling in `whoops` with your client's ID and secret."
            ).format(prefix=ctx.prefix)
        )
        return

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

    @serverset.command(name="images")
    @commands.admin()
    @commands.guild_only()
    async def serverset_images(self, ctx: commands.Context):
        """Toggle scoreboard images on or off."""
        enabled = await self.config.guild(ctx.guild).sb_image()
        if enabled:
            await self.config.guild(ctx.guild).sb_image.set(False)
            await ctx.send(_("Images disabled."), ephemeral=True)
        else:
            await self.config.guild(ctx.guild).sb_image.set(True)
            await ctx.send(_("Images enabled."), ephemeral=True)

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
        regions = ("us", "eu", "kr")
        if region.lower() not in regions:
            await ctx.send(
                _("That region does not exist.\nValid regions are: {regions}.").format(
                    regions=", ".join(regions)
                )
            )
            return
        await self.config.user(ctx.author).wow_character_region.set(region)
        await ctx.send(_("Character region set."))

    @serverset.command(
        name="onmessage",
        description="Toggle the bot's ability to respond to messages when a supported spell/item name is mentioned.",
    )
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def serverset_on_message(self, ctx: commands.Context):
        """Toggle the bot's ability to respond to messages when a supported spell/item name is mentioned.

        Example: `I think [[Ebon Might]] is cool.`"""
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

    @serverset.command(name="patchcountdown")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True, manage_channels=True)
    async def serverset_patchcountdown(self, ctx: commands.Context):
        "Add or remove a locked channel that will display the time until the next patch releases."
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

        now = datetime.datetime.now(datetime.UTC)

        diff = self.early_access_time - now
        early_access = True
        if diff.total_seconds() < 0:
            diff = self.release_time - now
            early_access = False
        if diff.total_seconds() < 0:
            await ctx.send(_("New season has already released."))
            return

        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, __ = divmod(remainder, 60)
        if diff.days > 0:
            time_str = f"{days}d{hours}h{minutes}m"
        else:
            time_str = f"{hours}h {minutes}m"

        channel_name = (
            _("🔴Patch in {countdown}").format(countdown=time_str)
            if early_access
            else _("🟡Season in {countdown}").format(countdown=time_str)
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

            now = datetime.datetime.now(datetime.UTC)

            diff = self.early_access_time - now
            early_access = True
            if diff.total_seconds() < 0:
                diff = self.release_time - now
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
                _("🔴Patch in {countdown}").format(countdown=time_str)
                if early_access
                else _("🟡Season in {countdown}").format(countdown=time_str)
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
        region: str,
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

        guild_data = await self.raiderio_api.get_guild_profile(
            region,
            realm,
            guild,
            fields=["raid_progression"],
        )
        try:
            guild: str = guild_data["name"]
            progress: str = guild_data["raid_progression"][self.current_raid]["summary"]
        except KeyError:
            return False
        activity = discord.CustomActivity(name=f"{guild}: {progress}", emoji=emoji)
        await self.bot.change_presence(activity=activity)
        return True

    @tasks.loop(minutes=60)
    async def update_bot_status(self):
        if not await self.set_bot_status():
            log.debug("Setting the bot's status failed.")

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name: str, api_tokens: Mapping[str, str]):
        """
        Lifted shamelessly from GHC.
        Thanks Kowlin for this
        """
        if service_name != "blizzard":
            return
        await self.create_bnet_objs()

    async def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.update_dungeon_scoreboard.cancel()
        self.guild_log.cancel()
        self.update_countdown_channels.cancel()
        self.update_bot_status.cancel()
        log.info("All tasks cancelled.")

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()
