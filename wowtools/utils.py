from discord import app_commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import humanize_number

from .autocomplete import REALMS

_ = Translator("WoWTools", __file__)


# async def get_api_client(bot: Red, region: str) -> WowApi:
#     """
#     Get Blizzard API client.
#
#     :param bot:
#     :param region:
#     :return: WoW API client
#     """
#     blizzard_api = await bot.get_shared_api_tokens("blizzard")
#     cid = blizzard_api.get("client_id")
#     secret = blizzard_api.get("client_secret")
#     if not cid or not secret:
#         raise ValueError(
#             _(
#                 "The Blizzard API is not properly set up.\n"
#                 "Create a client on https://develop.battle.net/ and then type in "
#                 "`{prefix}set api blizzard client_id,whoops client_secret,whoops` "
#                 "filling in `whoops` with your client's ID and secret."
#             )
#         )
#     return WowApi(client_id=cid, client_secret=secret, client_region=region)


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


async def get_realms(current):
    realms = []
    for realm in REALMS.keys():
        if current.lower() not in realm.lower():
            continue
        if len(REALMS[realm]) == 1:
            realms.append(app_commands.Choice(name=realm, value=f"{realm}:{REALMS[realm][0]}"))
        else:
            realms.extend(
                app_commands.Choice(name=f"{realm} ({region})", value=f"{realm}:{region}")
                for region in REALMS[realm]
            )
    return realms


# Undermine.exchange

import struct


def read_item_state(data: bytes) -> dict:
    # Constants
    VERSION_ITEM_STATE = 5
    MS_SEC = 1000
    COPPER_SILVER = 100
    MS_DAY = 86400000

    view = memoryview(data)
    offset = 0

    def read(byte_count):
        nonlocal offset
        result = offset
        offset += byte_count
        return result

    version = struct.unpack_from("B", view, read(1))[0]
    full_modifiers = True
    daily_history = True

    if version == 3:
        full_modifiers = False
    elif version == 4:
        daily_history = False
    elif version != VERSION_ITEM_STATE:
        raise ValueError("Unknown data version for item state.")

    result = {}

    result["snapshot"] = struct.unpack_from("<I", view, read(4))[0] * MS_SEC
    result["price"] = struct.unpack_from("<I", view, read(4))[0] * COPPER_SILVER
    result["quantity"] = struct.unpack_from("<I", view, read(4))[0]

    result["auctions"] = []
    for _ in range(struct.unpack_from("<H", view, read(2))[0]):
        price = struct.unpack_from("<I", view, read(4))[0] * COPPER_SILVER
        quantity = struct.unpack_from("<I", view, read(4))[0]
        result["auctions"].append({"price": price, "quantity": quantity})
    result["auctions"].sort(key=lambda x: x["price"])

    result["specifics"] = []
    for _ in range(struct.unpack_from("<H", view, read(2))[0]):
        price = struct.unpack_from("<I", view, read(4))[0] * COPPER_SILVER
        modifiers = {}
        if full_modifiers:
            for _ in range(struct.unpack_from("B", view, read(1))[0]):
                type_ = struct.unpack_from("<H", view, read(2))[0]
                value = struct.unpack_from("<I", view, read(4))[0]
                modifiers[type_] = value
        else:
            level = struct.unpack_from("B", view, read(1))[0]
            if level:
                modifiers["timewalker_level"] = level

        bonuses = [
            struct.unpack_from("<H", view, read(2))[0]
            for _ in range(struct.unpack_from("B", view, read(1))[0])
        ]
        bonuses.sort()
        result["specifics"].append({"price": price, "modifiers": modifiers, "bonuses": bonuses})
    result["specifics"].sort(key=lambda x: x["price"])

    result["snapshots"] = []
    deltas = {}
    prev_delta = None
    for _ in range(struct.unpack_from("<H", view, read(2))[0]):
        snapshot = struct.unpack_from("<I", view, read(4))[0] * MS_SEC
        price = struct.unpack_from("<I", view, read(4))[0] * COPPER_SILVER
        quantity = struct.unpack_from("<I", view, read(4))[0]
        deltas[snapshot] = {"snapshot": snapshot, "price": price, "quantity": quantity}

        if deltas[snapshot]["quantity"] == 0 and prev_delta and deltas[snapshot]["price"] == 0:
            deltas[snapshot]["price"] = prev_delta["price"]
        if not prev_delta:
            prev_delta = deltas[snapshot]

    result["daily"] = []
    if daily_history:
        for _ in range(struct.unpack_from("<H", view, read(2))[0]):
            snapshot = struct.unpack_from("<H", view, read(2))[0] * MS_DAY
            price = struct.unpack_from("<I", view, read(4))[0] * COPPER_SILVER
            quantity = struct.unpack_from("<I", view, read(4))[0]
            day_state = {"snapshot": snapshot, "price": price, "quantity": quantity}

            if result["daily"]:
                prev_seen = result["daily"][-1]
                lost_day = prev_seen["snapshot"] + MS_DAY
                while lost_day < day_state["snapshot"]:
                    result["daily"].append(
                        {"snapshot": lost_day, "price": prev_seen["price"], "quantity": 0}
                    )
                    lost_day += MS_DAY

            result["daily"].append(day_state)

    return result
