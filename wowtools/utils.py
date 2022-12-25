from aiowowapi import WowApi
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import humanize_number

_ = Translator("WoWTools", __file__)


async def get_api_client(bot: Red, ctx: commands.Context, region: str) -> WowApi:
    """
    Get Blizzard API client.

    :param bot:
    :param ctx:
    :param region:
    :return: WoW API client
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
            ).format(prefix="" if ctx.interaction else ctx.clean_prefix)
        )
    return WowApi(client_id=cid, client_secret=secret, client_region=region)


def format_to_gold(price: int, emotes: dict = None) -> str:
    """
    Format an int to a WoW gold string with emotes.

    :param price:
    :param emotes:
    :return: String containing gold price and emotes if provided.
    """
    price = str(price)
    gold_text = ""
    silver_text = ""
    copper_text = ""

    gold_emoji = emotes["gold"] if emotes else None
    silver_emoji = emotes["silver"] if emotes else None
    copper_emoji = emotes["copper"] if emotes else None

    gold = humanize_number(int(price[:-4])) if price[:-4] else "00"
    if gold != "00":
        gold_text = f"{gold}g" if gold_emoji is None else gold + gold_emoji

    silver = price[-4:-2]
    if silver != "00":
        silver_text = f"{silver}s" if silver_emoji is None else silver + silver_emoji

    copper = price[-2:]
    if copper != "00":
        copper_text = f"{copper}c" if copper_emoji is None else copper + copper_emoji

    return gold_text + silver_text + copper_text
