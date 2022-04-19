from typing import Any

from blizzardapi import BlizzardApi
from redbot.core import commands
from redbot.core.i18n import Translator

_ = Translator("WoWTools", __file__)


class Blizzard:
    async def get_api_client(self: Any, ctx: commands.Context) -> BlizzardApi:
        """
        Get Blizzard API client.

        :param ctx:
        :return: Blizzard API client
        """
        blizzard_api = await self.bot.get_shared_api_tokens("blizzard")
        cid = blizzard_api.get("client_id")
        secret = blizzard_api.get("client_secret")
        if not cid or not secret:
            raise ValueError(
                _(
                    "The Blizzard API is not properly set up.\n"
                    "Create a client on https://develop.battle.net/ and then type in "
                    "`{prefix}set api blizzard client_id,whoops client_secret,whoops` "
                    "filling in `whoops` with your client's ID and secret."
                ).format(prefix=ctx.prefix)
            )
        api_client = BlizzardApi(cid, secret)
        return api_client
