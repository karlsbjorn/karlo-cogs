import logging
from datetime import datetime, timedelta
from typing import Literal

import aiohttp
import discord
from aiolimiter import AsyncLimiter
from pyotp import TOTP
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n

from .auctionhouse import AuctionHouse
from .guildmanage import GuildManage
from .pvp import PvP
from .raiderio import Raiderio
from .scoreboard import Scoreboard
from .token import Token
from .wowaudit import Wowaudit

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)

# TODO: GIGA TODO - Swap to using [aiowowapi](https://github.com/Adalyia/aiowowapi), preferably before 3.5

try:  # python-bna doesn't work on Red 3.4 by default due to `click` being too old
    import bna
except Exception as e:
    log.warning(f"Failed to import bna: {e}\n`[p]battlenet` commands will not work.")


@cog_i18n(_)
class WoWTools(
    PvP, Raiderio, Token, Wowaudit, GuildManage, AuctionHouse, Scoreboard, commands.Cog
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
        }
        default_guild = {
            "region": None,
            "realm": None,
            "real_guild_name": None,
            "gmanage_guild": None,
            "gmanage_realm": None,
            "guild_roles": {},
            "old_sb": None,
            "scoreboard_channel": None,
            "scoreboard_message": None,
            "scoreboard_blacklist": [],
            "sb_image": False,
        }
        default_user = {
            "wow_character_name": None,
            "wow_character_realm": None,
            "wow_character_region": None,
            "auth_serial": None,
            "auth_secret": None,
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)
        self.limiter = AsyncLimiter(100, time_period=1)
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Red-DiscordBot/WoWToolsCog"}
        )
        self.update_dungeon_scoreboard.start()

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
                        _(
                            "That region does not exist.\nValid regions are: {regions}."
                        ).format(regions=", ".join(regions))
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

    @wowset.command(name="wowaudit_sheet")
    @commands.is_owner()
    async def wowset_wowaudit_sheet(self, ctx: commands.Context, key: str = None):
        """Set the key of your wowaudit spreadsheet."""
        try:
            async with ctx.typing():
                if key is None:
                    await self.config.wowaudit_key.clear()
                    await ctx.send(_("WowAudit spreadsheet key cleared."))
                    return
                await self.config.wowaudit_key.set(key)
            await ctx.send(_("WowAudit spreadsheet key set."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @wowset.command(name="service_account")
    @commands.is_owner()
    async def wowset_service_account(self, ctx: commands.Context):
        """Set the service account key for the bot. This is required for any wowaudit commands."""
        if ctx.message.guild is not None:
            await ctx.send(_("This command can only be used in DMs."))
            return

        s_account_guide = _(
            "A service account is a special type of Google account intended to represent a non-human user"
            " that needs to authenticate and be authorized to access data in Google APIs.\n"
            "Since it’s a separate account, by default it does not have access to any spreadsheet until you share"
            " it with this account. Just like any other Google account.\n\n"
            "Here’s how to get one:\n"
            "1. Go to https://console.developers.google.com/\n"
            "2. In the box labeled “Search for APIs and Services”, search for “Google Drive API” and enable it.\n"
            "3. In the box labeled “Search for APIs and Services”, search for “Google Sheets API” and enable it.\n"
            "4. Go to “APIs & Services > Credentials” and choose “Create credentials > Service account key”.\n"
            "5. Fill out the form\n"
            "6. Click “Create” and “Done”.\n"
            "7. Press “Manage service accounts” above Service Accounts.\n"
            "8.  Press on ⋮ near recently created service account and select “Manage keys” and then click on"
            " “ADD KEY > Create new key”.\n"
            "9. Select JSON key type and press “Create”.\n\n"
            "You will automatically download a JSON file with credentials.\nAttach that file with the command you"
            " just typed."
        )

        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                if attachment.filename == "service_account.json":
                    await attachment.save(
                        str(cog_data_path(self)) + "/service_account.json"
                    )
                    await ctx.send(_("Service account set."))
                else:
                    await ctx.send(s_account_guide)
        else:
            await ctx.send(s_account_guide)

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
                _("{currency} emote set to {emoji}").format(
                    currency=currency.title(), emoji=emoji
                )
            )
        else:
            await self.config.emotes.set_raw(currency, value=None)
            await ctx.send(
                _("{currency} emote removed.").format(currency=currency.title())
            )

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

    @commands.group()
    async def battlenet(self, ctx: commands.Context):
        """Battle.net authenticator commands."""
        pass

    @battlenet.command(name="set")
    async def battlenet_set(self, ctx: commands.Context):
        """Set up the authenticator."""
        async with ctx.typing():
            try:
                serial, secret = bna.request_new_serial("EU")
            except bna.HTTPError as e:
                await ctx.send(_("Could not connect: {error}").format(error=e))
                return
            await self.config.user(ctx.author).auth_serial.set(serial)
            await self.config.user(ctx.author).auth_secret.set(secret)
            await ctx.author.send(
                "Your serial is: **{serial}**\nYour secret is: **{secret}**".format(
                    serial=serial, secret=secret
                )
            )

            totp = TOTP(secret, digits=8)
        await ctx.send(
            _("Authenticator set.\nYour code is: **{code}**").format(code=totp.now())
        )

    @battlenet.command(name="code")
    async def battlenet_code(self, ctx: commands.Context):
        """Get your authenticator code."""
        secret = await self.config.user(ctx.author).auth_secret()
        if not secret:
            await ctx.send(_("You haven't set up the authenticator yet."))
            return
        totp = TOTP(secret, digits=8)

        now = datetime.now()
        expiry = now + (datetime.min - now) % timedelta(seconds=30)

        await ctx.send(
            _("Your code is: **{code}**\nIt expires {time}").format(
                code=totp.now(), time=f"<t:{int(expiry.timestamp())}:R>"
            )
        )

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.update_dungeon_scoreboard.stop()

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()
