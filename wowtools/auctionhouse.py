from datetime import datetime
from typing import Dict

import discord
from redbot.core import commands
from redbot.core.i18n import Translator

from .utils import format_to_gold, get_api_client

_ = Translator("WoWTools", __file__)


class AuctionHouse:
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    @commands.command()
    async def price(self, ctx: commands.Context, *, item: str):
        """Get the current market price of an item."""
        async with ctx.typing():
            config_region: str = await self.config.guild(ctx.guild).region()
            if not config_region:
                await ctx.send(
                    _(
                        "Please set a region with `{prefix}wowset region` before using this command."
                    ).format(prefix=ctx.clean_prefix)
                )
                return
            if config_region in ("cn", "tw"):
                await ctx.send(
                    _(
                        "The Auction House is not available in China or Taiwan.\n"
                        "Please set a different region with `{prefix}wowset region`."
                    ).format(prefix=ctx.clean_prefix)
                )
                return

            try:
                api_client = await get_api_client(self.bot, ctx, config_region)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))
                return

            config_realm: str = await self.config.guild(ctx.guild).realm()
            if not config_realm:
                await ctx.send(
                    _(
                        "Please set a realm with `{prefix}wowset realm` before using this command."
                    ).format(prefix=ctx.clean_prefix)
                )
                return
            boe_disclaimer = False

            async with api_client as wow_client:
                wow_client = wow_client.Retail
                # Search for the item
                await self.limiter.acquire()
                items = await wow_client.GameData.get_item_search(
                    {"name.en_US": item, "_pageSize": 1000}
                )

                results: Dict = items["results"]
                found_items: Dict[int, str] = {}
                for result in results:
                    item_id: int = result["data"]["id"]
                    item_name: str = result["data"]["name"]["en_US"]
                    if found_items:
                        if item_name in found_items.values():
                            continue
                    elif item.lower() in item_name.lower():
                        item = item_name  # Use the exact name for all further searches
                        found_items[item_id] = item_name
                if not found_items:
                    await ctx.send(_("No results found."))
                    return

                # Get connected realm ID
                await self.limiter.acquire()
                c_realms = await wow_client.GameData.get_connected_realms_search(
                    {"_pageSize": 1000}
                )

                c_realm_id = None
                results: Dict = c_realms["results"]
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
                await self.limiter.acquire()
                auctions_data: Dict = await wow_client.GameData.get_auctions(
                    connected_realm_id=c_realm_id
                )

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
                    # Item could be a commodity
                    await self.limiter.acquire(25)
                    commodities_data: Dict = (
                        await wow_client.GameData.get_commodity_auctions()
                    )
                    auctions = commodities_data["auctions"]
                    for auction in auctions:
                        item_id = auction["item"]["id"]
                        if item_id in found_items:
                            item_name = found_items[item_id]
                            found_item_id = item_id
                            item_quantity += auction["quantity"]
                            item_price = auction["unit_price"]
                            prices.append(item_price)
                if not prices:
                    await ctx.send(_("No auctions could be found for this item."))
                    return

                # Embed stuff
                # Get item icon
                await self.limiter.acquire()
                item_media = await wow_client.GameData.get_item_media(
                    item_id=found_item_id
                )
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
                gold_emotes: Dict = await self.config.emotes()
                min_buyout = format_to_gold(min(prices), gold_emotes)
                embed.add_field(name=_("Min Buyout"), value=min_buyout)
                embed.add_field(name=_("Current quantity"), value=str(item_quantity))
                if boe_disclaimer:
                    embed.add_field(
                        name=_("Warning"),
                        value=_(
                            "The expected price of this item may be incorrect due to\n"
                            "item level differences or other factors."
                        ),
                        inline=False,
                    )
                embed.add_field(
                    name="\N{ZERO WIDTH SPACE}",
                    value=_(
                        "[Detailed info](https://theunderminejournal.com/#{region}/{realm}/item/{item_id})"
                    ).format(
                        region=config_region,
                        realm=config_realm,
                        item_id=found_item_id,
                    ),
                    inline=False,
                )

        await ctx.send(embed=embed)


# TODO: [p]stackprice [item]
# TODO: [p]craftprice [item]
