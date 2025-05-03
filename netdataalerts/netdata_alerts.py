import logging

import aiohttp
import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

from netdataalerts.alarm import Alarm

log = logging.getLogger("red.karlo-cogs.netdata-alerts")
_ = Translator("NetdataAlerts", __file__)


@cog_i18n(_)
class NetdataAlerts(commands.Cog):
    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=87446677010550784, force_registration=True)
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Red-DiscordBot/karlo-cogs/NetdataAlertsCog"}
        )
        default_global = {"only_critical": False}
        self.config.register_global(**default_global)
        self.netdata_base = self.form_netdata_base()
        self.prev_alarms: set[int] = set()
        self.current_alarms: set[int] = set()

    def form_netdata_base(self):
        # use bot config
        host = "127.0.0.1"
        port = 19999  # default port
        return f"http://{host}:{port}"

    async def netdata_running(self) -> bool:
        request_url = f"{self.netdata_base}/api/v1/info"
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                return False
            return True

    async def cog_load(self) -> None:
        if not await self.netdata_running():
            raise NetdataNotRunning
        self.check_alarms.start()

    @commands.group()
    @commands.is_owner()
    async def netdataset(self, ctx: commands.Context):
        """Change NetdataAlerts settings."""
        pass

    @netdataset.command(name="critical")
    async def netdataset_critical(self, ctx: commands.Context):
        only_critical = await self.config.only_critical()
        if only_critical:
            await self.config.only_critical.set(False)
            await ctx.send(
                _("NetdataAlerts will now send notifications for all alerts"),
                silent=True,
            )
        else:
            await self.config.only_critical.set(True)
            await ctx.send(
                _("NetdataAlerts will now send notifications only for critical alerts"),
                silent=True,
            )

    # The server is local so there's no issue spamming the endpoint
    @tasks.loop(seconds=5)
    async def check_alarms(self):
        self.prev_alarms, self.current_alarms = self.current_alarms, set()
        alarms = await self.get_current_alarms()
        if not alarms:
            return
        embeds: list[discord.Embed] = []
        critical = False
        for key, alarm_data in alarms.items():
            alarm = Alarm.model_validate(alarm_data)
            if alarm.id in self.prev_alarms:
                self.current_alarms.add(alarm.id)
                continue
            if alarm.status != "CRITICAL" and await self.config.only_critical():
                continue
            embeds.append(
                discord.Embed(
                    title=alarm.summary,
                    description=self.make_description(alarm),
                    colour=alarm.get_status_color(),
                ).set_author(name="Netdata")
            )
            if alarm.status == "CRITICAL":
                critical = True
            self.current_alarms.add(alarm.id)
        if not embeds:
            return
        destinations = await self.bot.get_owner_notification_destinations()
        for dest in destinations:
            await dest.send(embeds=embeds, silent=not critical)

    def make_description(self, alarm: Alarm) -> str:
        return f"{alarm.info}\nValue: {alarm.value_string}\n<t:{alarm.last_status_change}:R>"

    async def get_current_alarms(self) -> dict:
        request_url = f"{self.netdata_base}/api/v1/alarms"
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                return {}
            data: dict = await resp.json()
            if not data.get("status"):
                return {}
            return data.get("alarms", [])

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.check_alarms.stop()


class NetdataNotRunning(Exception):
    pass
