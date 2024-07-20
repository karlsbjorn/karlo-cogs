from datetime import datetime, timezone
from typing import Dict, List

import discord
from redbot.core import app_commands
from redbot.core.i18n import Translator

from wowtools.utils import format_to_gold, get_realms

_ = Translator("WoWTools", __file__)


class UserInstallableAuctionHouse:
    @app_commands.command(name="price")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        item="Exact name of the item to search for", realm="Realm's auction house to search in"
    )
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
            wow_client = wow_client.Retail
            # Search for the item
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
                await interaction.followup.send(_("No results found."))
                return

            # Get connected realm ID
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
            if not prices:
                await interaction.followup.send(_("No auctions could be found for this item."))
                return

            # Embed stuff
            # Get item icon
            await self.limiter.acquire()
            item_media = await wow_client.GameData.get_item_media(item_id=found_item_id)
            item_icon_url = item_media["assets"][0]["value"]

            # Create embed
            embed_title = _("Price: {item}").format(item=item_name)
            embed_url = f"https://www.wowhead.com/item={found_item_id}"
            embed = discord.Embed(
                title=embed_title,
                url=embed_url,
                colour=discord.Colour.blurple(),
                timestamp=datetime.now(timezone.utc),
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

            details_url = (
                f"https://oribos.exchange/#" f"{region}-" f"{config_realm}/" f"{found_item_id}"
            )
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label=_("More details"), style=discord.ButtonStyle.link, url=details_url
                )
            )

        await interaction.followup.send(embed=embed, view=view)

    @user_install_price.autocomplete("realm")
    async def user_install_price_realm_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        realms = await get_realms(current)
        return realms[:25]
