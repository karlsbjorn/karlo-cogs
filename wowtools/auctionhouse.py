import functools
from datetime import datetime
from typing import Dict

import discord
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
            if not config_region:
                await ctx.send(
                    _(
                        "Please set a region with `{prefix}wowset region` before using this command."
                    ).format(prefix=ctx.prefix)
                )
                return
            config_realm: str = await self.config.guild(ctx.guild).realm()
            if not config_realm:
                await ctx.send(
                    _(
                        "Please set a realm with `{prefix}wowset realm` before using this command."
                    ).format(prefix=ctx.prefix)
                )
                return
            boe_disclaimer = False

            # Search for the item
            fetch_items = functools.partial(
                api_client.wow.game_data.get_item_search,
                region=config_region,
                locale="en_US",
                item_name=item,
                page_size=1000,
                is_classic=False,
            )
            items = await self.bot.loop.run_in_executor(None, fetch_items)

            results: Dict = items["results"]
            found_items: Dict[int, str] = {}
            for result in results:
                item_id = result["data"]["id"]
                item_name = result["data"]["name"]["en_US"]
                if item.lower() in item_name.lower():
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
            item_quantity = 0
            for auction in auctions:
                item_id = auction["item"]["id"]
                if item_id in found_items:
                    item_name = found_items[item_id]
                    found_item_id = item_id
                    item_quantity += auction["quantity"]
                    try:
                        item_price = auction["unit_price"]
                    except KeyError:
                        item_price = auction["buyout"]
                        boe_disclaimer = True
                    prices.append(item_price)
            if not prices:
                await ctx.send(_("No auctions for this item could be found."))
                return

            # Embed stuff
            # Get item icon
            fetch_media = functools.partial(
                api_client.wow.game_data.get_item_media,
                region=config_region,
                locale="en_US",
                item_id=found_item_id,
            )
            item_media = await self.bot.loop.run_in_executor(None, fetch_media)
            item_icon_url = item_media["assets"][0]["value"]

            # Create embed
            embed_title = _("Price: {item}").format(item=item_name)
            embed_url = f"https://www.wowhead.com/item={found_item_id}"
            embed = discord.Embed(
                title=embed_title,
                url=embed_url,
                colour=await ctx.embed_color(),
                timestamp=datetime.utcnow(),
            )
            embed.set_thumbnail(url=item_icon_url)
            min_buyout = format_to_gold(min(prices))
            embed.add_field(name=_("Min Buyout"), value=min_buyout)
            embed.add_field(name=_("Current quantity"), value=str(item_quantity))
            if boe_disclaimer:
                embed.add_field(
                    name=_("Warning"),
                    value=_(
                        "This item is a BoE and the price may be incorrect due to item level differences."
                    ),
                    inline=False,
                )

            await ctx.send(embed=embed)


# TODO: [p]stackprice [item]
# TODO: [p]craftprice [item]
