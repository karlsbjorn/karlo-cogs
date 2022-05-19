import functools

import discord
from redbot.core import commands
from redbot.core.i18n import Translator

from .utils import format_to_gold, get_api_client

_ = Translator("WoWTools", __file__)

VALID_REGIONS = ("eu", "us", "kr")


class Token:
    @commands.command()
    async def tokenprice(self, ctx: commands.Context, region: str = "all"):
        """Check price of WoW token in a region"""
        async with ctx.typing():
            if region == "all":
                await self.priceall(ctx)
                return
            api_client = await get_api_client(self.bot, ctx)

            if region not in VALID_REGIONS and region != "all":
                raise ValueError(
                    _("Invalid region. Valid regions are: `eu`, `us`, `kr` or `all`.")
                )

            fetch_token = functools.partial(
                api_client.wow.game_data.get_token_index,
                region=region,
                locale="en_US",
            )
            wow_token = await self.bot.loop.run_in_executor(None, fetch_token)
            token_price = str(wow_token["price"])

            gold_emotes = await self.config.emotes()
            message = _(
                "Current price of the {region} WoW Token is: **{gold}**"
            ).format(
                region=region.upper(), gold=format_to_gold(token_price, gold_emotes)
            )

            embed = discord.Embed(description=message, colour=await ctx.embed_colour())
        await ctx.send(embed=embed)

    async def priceall(self, ctx):
        """Check price of the WoW token in all supported regions"""
        async with ctx.typing():
            try:
                api_client = await get_api_client(self.bot, ctx)

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
                    gold_emotes = await self.config.emotes()
                    embed.add_field(
                        name=region.upper(),
                        value=format_to_gold(token_price, gold_emotes),
                    )
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))
