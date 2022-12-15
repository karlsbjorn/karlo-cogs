import asyncio
import binascii
import logging
from datetime import datetime, timedelta
from typing import Literal

import bna
from pyotp import TOTP
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.predicates import MessagePredicate

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
            "auth_restore": None,
        }
        self.config.register_user(**default_user)

    @commands.group()
    async def battlenet(self, ctx: commands.Context):
        """Battle.net authenticator commands."""
        pass

    @commands.dm_only()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    @battlenet.command(name="set")
    async def battlenet_set(self, ctx: commands.Context, serial: str = None, secret: str = None):
        """Set up the authenticator."""
        await ctx.send(
            _(
                "The owner of this bot will have **full access** to your authenticator details.\n"
                "If you do not fully trust the owner of this bot with this information, do not use this command.\n"
                "If you are sure you want to continue, type `yes`. Otherwise, type `no`."
            )
        )
        try:
            predicate = MessagePredicate.yes_or_no(ctx, user=ctx.author)
            await ctx.bot.wait_for("message", check=predicate, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send(_("Assuming `no`."))
            return
        async with ctx.typing():
            if (serial or secret) and not (serial and secret):
                await ctx.send_help()
                return
            try:
                if not serial and not secret:
                    serial, secret = bna.request_new_serial("EU")
                try:
                    restore_code = bna.get_restore_code(serial, secret)
                except binascii.Error:
                    await ctx.send(_("Invalid serial or secret."))
                    return
            except bna.HTTPError as e:
                await ctx.send(_("Could not connect: {error}").format(error=e))
                return
            await self.config.user(ctx.author).auth_serial.set(serial)
            await self.config.user(ctx.author).auth_secret.set(secret)
            await self.config.user(ctx.author).auth_restore.set(restore_code)
            await ctx.send(
                _(
                    "Your serial is: **{serial}**\n"
                    "Your secret is: **{secret}**\n"
                    "Your restore code is: **{restore_code}**\n\n"
                    "You should backup this information somewhere else, like a mobile authenticator app.".format(
                        serial=serial, secret=secret, restore_code=restore_code
                    )
                )
            )

            totp = TOTP(secret, digits=8)
        await ctx.send(_("Authenticator set.\nYour code is: **{code}**").format(code=totp.now()))

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
