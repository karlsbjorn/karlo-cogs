import logging
from datetime import datetime, timedelta
from typing import Literal

import bna
from pyotp import TOTP
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

log = logging.getLogger("red.karlo-cogs.battlenetauth")
_ = Translator("BattleNetAuth", __file__)


@cog_i18n(_)
class BattleNetAuth(commands.Cog):
    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=87446677010550784)
        default_user = {
            "auth_serial": None,
            "auth_secret": None,
        }
        self.config.register_user(**default_user)

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

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()
