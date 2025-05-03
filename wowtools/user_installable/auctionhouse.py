from datetime import datetime, timezone
from typing import Dict, List, Optional

import discord
from aiowowapi import RetailApi
from redbot.core import app_commands
from redbot.core.i18n import Translator

from wowtools.utils import format_to_gold, get_realms

_ = Translator("WoWTools", __file__)


class UserInstallableAuctionHouse:
    @app_commands.command(name="price")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        item="Exact name of the item to search for",
        realm="Realm's auction house to search in",
    )
    @app_commands.default_permissions(embed_links=True)
    async def user_install_price(self, interaction: discord.Interaction, item: str, realm: str):
        """Get the current auction price of an item."""
        realm, region = realm.split(sep=":")
        config_realm = (
            "-".join(realm).lower() if isinstance(realm, tuple) else realm.lower()
        ).replace(" ", "-")
        region = region.lower()

        boe_disclaimer = False
        await interaction.response.defer()
        async with self.blizzard.get(region) as wow_client:
            if not wow_client:
                await interaction.followup.send("Blizzard API not properly set up.")
                return
            wow_client: RetailApi = wow_client.Retail

            found_items = await self.search_for_item(item, wow_client)
            if not found_items:
                await interaction.followup.send(_("No results found."))
                return

            c_realm_id = await self.get_connected_realm_id(config_realm, wow_client)
            if not c_realm_id:
                await interaction.followup.send(_("Could not find realm."))
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
                commodities_data: Dict = await wow_client.GameData.get_commodities()
                auctions = commodities_data["auctions"]
                for auction in auctions:
                    item_id = auction["item"]["id"]
                    if item_id in found_items:
                        item_name = found_items[item_id]
                        found_item_id = item_id
                        item_quantity += auction["quantity"]
                        item_price = auction["unit_price"]
                        prices.append(item_price)
                listings_str = await self.get_undermine_commodity_listings(region, found_item_id)
            if not prices:
                await interaction.followup.send(_("No auctions could be found for this item."))
                return

            # Embed stuff
            # Get item icon
            await self.limiter.acquire()
            item_media = await wow_client.GameData.get_item_media(item_id=found_item_id)
            item_icon_url = item_media["assets"][0]["value"]

            # Create embed
            gold_emotes: Dict = await self.config.emotes()
            embed_title = _("Price: {item}").format(item=item_name)
            embed_url = f"https://www.wowhead.com/item={found_item_id}"
            embed = discord.Embed(
                title=embed_title,
                url=embed_url,
                colour=discord.Colour.blurple(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_thumbnail(url=item_icon_url)
            min_buyout = format_to_gold(min(prices), gold_emotes)
            embed.add_field(name=_("Min Buyout"), value=min_buyout)
            embed.add_field(name=_("Current quantity"), value=str(item_quantity))
            if listings_str:
                embed.add_field(name=_("Current listings"), value=listings_str)
            if boe_disclaimer:
                embed.add_field(
                    name=_("Warning"),
                    value=_(
                        "The expected price of this item may be incorrect due to\n"
                        "item level differences or other factors."
                    ),
                    inline=False,
                )

            details_url = (
                f"https://oribos.exchange/#" f"{region}-" f"{config_realm}/" f"{found_item_id}"
            )
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label=_("More details"),
                    style=discord.ButtonStyle.link,
                    url=details_url,
                )
            )

        await interaction.followup.send(embed=embed, view=view)

    async def search_for_item(self, item, wow_client):
        items = await wow_client.GameData.get_item_search({"name.en_US": item, "_pageSize": 1000})

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
        return found_items

    async def get_connected_realm_id(self, config_realm: str, wow_client: RetailApi):
        c_realms = await wow_client.GameData.get_connected_realms_search({"_pageSize": 1000})

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
        return c_realm_id

    async def get_undermine_commodity_listings(
        self, region: str, found_item_id: int
    ) -> Optional[str]:
        # commodity_realms = {
        #     "us": 32512,
        #     "eu": 32513,
        #     "tw": 32514,
        #     "kr": 32515,
        # }

        # undermine_url = "https://undermine.exchange/"
        # url = [
        #     "data",
        #     "cached",
        #     str(commodity_realms[region.lower()]),
        #     str(found_item_id & 0xFF),
        #     f"{found_item_id}.bin",
        # ]
        # url = undermine_url + "/".join(url)

        # data_dict = {}
        # async with self.session.request("GET", url) as r:
        #     if r.status == 200:
        #         data = await r.content.read()
        #         data_dict = read_item_state(data)

        # gold_emotes: Dict = await self.config.emotes()
        # listing_count = 0
        # listings_str = ""
        # for listing in data_dict.get("auctions", []):
        #     if listing_count >= 7:
        #         break
        #     listings_str += (
        #         f"{format_to_gold(listing['price'], gold_emotes)} | {listing['quantity']}\n"
        #     )
        #     listing_count += 1
        listings_str = None
        return listings_str

    @user_install_price.autocomplete("realm")
    async def user_install_price_realm_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        realms = await get_realms(current)
        return realms[:25]
