import logging
from typing import Literal

import aiohttp
import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n

from .auctionhouse import AuctionHouse
from .guildmanage import GuildManage
from .pvp import PvP
from .raiderio import Raiderio
from .token import Token
from .wowaudit import Wowaudit

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)


@cog_i18n(_)
class WoWTools(PvP, Raiderio, Token, Wowaudit, GuildManage, AuctionHouse, commands.Cog):
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
            "scoreboard_channel": None,
            "scoreboard_message": None,
            "scoreboard_blacklist": [],
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Red-DiscordBot/WoWToolsCog"}
        )
        self.update_scoreboard.start()

    @commands.group()
    async def wowset(self, ctx):
        """Change WoWTools settings."""
        pass

    @wowset.command()
    @commands.admin()
    async def region(self, ctx: commands.Context, region: str):
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
                await self.config.guild(ctx.guild).region.set(region)
            await ctx.send(_("Region set succesfully."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @wowset.command()
    @commands.admin()
    async def realm(self, ctx: commands.Context, realm: str = None):
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

    @wowset.command()
    @commands.is_owner()
    async def wowaudit_sheet(self, ctx: commands.Context, key: str = None):
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

    @wowset.command()
    @commands.is_owner()
    async def service_account(self, ctx: commands.Context):
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

    @wowset.command()
    @commands.is_owner()
    async def blizzard(self, ctx: commands.Context):
        """Instructions for setting up the Blizzard API."""
        return await ctx.send(
            _(
                "Create a client on https://develop.battle.net/ and then type in "
                "`{prefix}set api blizzard client_id,whoops client_secret,whoops` "
                "filling in `whoops` with your client's ID and secret."
            ).format(prefix=ctx.prefix)
        )

    @wowset.command()
    @commands.is_owner()
    async def emote(
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

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.update_scoreboard.stop()

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        return
