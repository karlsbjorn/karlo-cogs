import aiohttp
from redbot.core import Config, commands
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n

from .raidbots import Raidbots
from .raiderio import Raiderio
from .wowaudit import Wowaudit
from .wowpvp import Wowpvp
from .wowtoken import Wowtoken

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
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Red-DiscordBot/WoWToolsCog"}
        )

    @commands.group()
    async def wowset(self, ctx):
        """Change WoWTools settings."""
        pass

    @wowset.command()
    @commands.is_owner()
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
                await self.config.region.set(region)
                await ctx.send(_("Region set succesfully."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @wowset.command()
    @commands.is_owner()
    async def wowaudit(self, ctx: commands.Context, key: str = None):
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
    @commands.admin()
    async def raidbots(self, ctx: commands.Context):
        """Toggle automatic response to a Raidbots simulation report link."""
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
