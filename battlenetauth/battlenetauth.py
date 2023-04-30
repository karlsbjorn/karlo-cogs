import binascii
import logging
from datetime import datetime, timedelta
from typing import Literal

import bna
import discord
from pyotp import TOTP
from redbot.core import Config, app_commands, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

log = logging.getLogger("red.karlo-cogs.battlenetauth")
_ = Translator("BattleNetAuth", __file__)


@cog_i18n(_)
class BattleNetAuth(commands.Cog):
    slash_battlenet = app_commands.Group(
        name="battlenet", description="Battle.net authenticator commands."
    )

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=87446677010550784)
        default_user = {
            "auth_serial": None,
            "auth_secret": None,
            "auth_restore": None,
        }
        self.config.register_user(**default_user)

    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    @slash_battlenet.command(name="set")
    async def battlenet_set(self, interaction: discord.Interaction, serial: str, secret: str):
        """Set up the authenticator.

        Parameters
        ----------
        serial: str
            The serial number of the authenticator.
        secret: str
            The secret of the authenticator.
        """
        await interaction.response.defer(ephemeral=True)
        try:
            if not serial and not secret:
                serial, secret = bna.request_new_serial("EU")
            try:
                restore_code = bna.get_restore_code(serial, secret)
            except binascii.Error:
                await interaction.response.send_message(
                    _("Invalid serial or secret."), ephemeral=True
                )
                return
        except bna.HTTPError as e:
            await interaction.response.send_message(
                _("Could not connect: {error}").format(error=e), ephemeral=True
            )
            return
        await self.config.user(interaction.user).auth_serial.set(serial)
        await self.config.user(interaction.user).auth_secret.set(secret)
        await self.config.user(interaction.user).auth_restore.set(restore_code)
        await interaction.response.send_message(
            _(
                "Your serial is: **{serial}**\n"
                "Your secret is: **{secret}**\n"
                "Your restore code is: **{restore_code}**\n\n"
                "You should backup this information somewhere else, like a mobile authenticator app.".format(
                    serial=serial, secret=secret, restore_code=restore_code
                )
            ),
            ephemeral=True,
        )

    @slash_battlenet.command(name="code")
    async def battlenet_code(self, interaction: discord.Interaction):
        """Get your authenticator code."""
        await interaction.response.defer(ephemeral=True)
        secret = await self.config.user(interaction.user).auth_secret()
        if not secret:
            await interaction.response.send_message(
                _("You haven't set up the authenticator yet."), ephemeral=True
            )
            return
        totp = TOTP(secret, digits=8)

        now = datetime.now()
        expiry = now + (datetime.min - now) % timedelta(seconds=30)

        await interaction.response.send_message(
            _("Your code is: **{code}**\nIt expires {time}").format(
                code=totp.now(), time=f"<t:{int(expiry.timestamp())}:R>"
            ),
            ephemeral=True,
        )

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()
