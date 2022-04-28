import functools
from typing import Dict

from blizzardapi import BlizzardApi
from redbot.core import commands
from redbot.core.i18n import Translator

from .utils import format_to_gold, get_api_client

_ = Translator("WoWTools", __file__)


class AuctionHouse:
    @commands.command()
    async def price(self, ctx: commands.Context, *, item: str):
        """Get the current market price of an item."""
        # TODO: Add support for stack sizes
        async with ctx.typing():
            try:
                api_client: BlizzardApi = await get_api_client(self.bot, ctx)
            except ValueError as e:
                await ctx.send(str(e))
                return

            config_region: str = await self.config.region()
            config_realm: str = await self.config.guild(ctx.guild).realm()

            # Search for the item
            fetch_items = functools.partial(
                api_client.wow.game_data.get_item_search,
                region=config_region,
                locale="en_US",
                item_name=item,
                is_classic=False,
            )
            items = await self.bot.loop.run_in_executor(None, fetch_items)

            results: Dict = items["results"]
            found_items: Dict[int, str] = {}
            for result in results:
                item_id = result["data"]["id"]
                item_name = result["data"]["name"]["en_US"]
                found_items[item_id] = item_name
            if not found_items:
                await ctx.send(_("No results found."))
                return

            # Get connected realm ID
            fetch_c_realms = functools.partial(
                api_client.wow.game_data.get_connected_realms_search,
                region=config_region,
                locale="en_US",
                is_classic=False,
            )
            c_realms = await self.bot.loop.run_in_executor(None, fetch_c_realms)

            c_realm_id = None
            results = c_realms["results"]
            for result in results:
                c_realm_data = result["data"]
                realms = c_realm_data["realms"]
                for realm in realms:
                    realm_names = list(realm["name"].values())
                    realm_names = [name.lower() for name in realm_names]
                    if config_realm in realm_names:
                        c_realm_id = c_realm_data["id"]
            if not c_realm_id:
                await ctx.send(_("Could not find realm."))
                return

            # Get price of item
            fetch_auctions = functools.partial(
                api_client.wow.game_data.get_auctions,
                region=config_region,
                locale="en_US",
                connected_realm_id=c_realm_id,
            )
            auctions_data = await self.bot.loop.run_in_executor(None, fetch_auctions)

            auctions = auctions_data["auctions"]
            prices = []
            for auction in auctions:
                item_id = auction["item"]["id"]
                if item_id in found_items:
                    item_name = found_items[item_id]
                    try:
                        item_price = auction["unit_price"]
                    except KeyError:
                        item_price = auction["buyout"]
                    prices.append(item_price)

            # TODO: Make this an embed with item name, price, link, image, etc.
            await ctx.send(
                _("{item_name} is currently selling for {price}.").format(
                    item_name=item_name, price=format_to_gold(min(prices))
                )
            )
