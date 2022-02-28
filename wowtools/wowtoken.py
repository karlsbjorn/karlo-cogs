import functools
import discord
from redbot.core import commands
from redbot.core.i18n import Translator
from blizzardapi import BlizzardApi

_ = Translator("WoWTools", __file__)

VALID_REGIONS = ("eu", "us", "kr")


class Wowtoken:
    @commands.group()
    async def token(self, ctx):
        """Commands for interacting with the WoW token."""
        pass

    @token.command()
    async def price(self, ctx, region: str):
        """Check price of WoW token in a region"""
        async with ctx.typing():
            try:
                blizzard_api = await self.bot.get_shared_api_tokens("blizzard")
                cid = blizzard_api.get("client_id")
                secret = blizzard_api.get("client_secret")

                if not cid or not secret:
                    raise ValueError(_("The Blizzard API is not properly set up."))
                api_client = BlizzardApi(cid, secret)

                if region not in VALID_REGIONS:
                    raise ValueError(
                        _("Invalid region. Valid regions are: `eu`, `us` i `kr`.")
                    )

                fetch_token = functools.partial(
                    api_client.wow.game_data.get_token_index,
                    region=region,
                    locale="en_US",
                )
                wow_token = await self.bot.loop.run_in_executor(None, fetch_token)
                token_price = str(wow_token["price"])

                message = _(
                    "Current price of the {region} WoW Token is: **{gold}**"
                ).format(region=region.upper(), gold=self.format_to_gold(token_price))

                embed = discord.Embed(
                    description=message, colour=await ctx.embed_colour()
                )

                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @token.command()
    async def priceall(self, ctx):
        """Check price of the WoW token in all supported regions"""
        async with ctx.typing():
            try:
                blizzard_api = await self.bot.get_shared_api_tokens("blizzard")
                cid = blizzard_api.get("client_id")
                secret = blizzard_api.get("client_secret")

                if not cid or not secret:
                    raise ValueError(_("The Blizzard API is not properly set up."))
                api_client = BlizzardApi(cid, secret)

                embed = discord.Embed(
                    title=_("WoW Token prices"), colour=await ctx.embed_colour()
                )

                for region in VALID_REGIONS:
                    fetch_token = functools.partial(
                        api_client.wow.game_data.get_token_index,
                        region=region,
                        locale="en_US",
                    )
                    wow_token = await self.bot.loop.run_in_executor(None, fetch_token)
                    token_price = str(wow_token["price"])
                    embed.add_field(
                        name=region.upper(), value=self.format_to_gold(token_price)
                    )
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @staticmethod
    def format_to_gold(price) -> str:
        gold = price[:-4] + "g"
        # silver = price[-4:-2] + "s"
        # copper = price[-2:] + "c"
        return gold  # + silver + copper
