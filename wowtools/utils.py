from typing import Any

from blizzardapi import BlizzardApi
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator

_ = Translator("WoWTools", __file__)


async def get_api_client(bot: Red, ctx: commands.Context) -> BlizzardApi:
    """
    Get Blizzard API client.

    :param bot:
    :param ctx:
    :return: Blizzard API client
    """
    blizzard_api = await bot.get_shared_api_tokens("blizzard")
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


def format_to_gold(price) -> str:
    price = str(price)
    gold_text = ""
    silver_text = ""
    copper_text = ""

    gold = price[:-4]
    if gold != "00":
        gold_text = gold + "g"

    silver = price[-4:-2]
    if silver != "00":
        silver_text = silver + "s"

    copper = price[-2:]
    if copper != "00":
        copper_text = copper + "c"

    return gold_text + silver_text + copper_text
