import discord
from redbot.core import commands
from redbot.core.i18n import Translator

from .utils import format_to_gold, get_api_client

_ = Translator("WoWTools", __file__)

VALID_REGIONS = ("eu", "us", "kr", "cn")


class Token:
    @commands.hybrid_command()
    async def wowtoken(self, ctx: commands.Context, region: str = "all"):
        """Check price of WoW token in a region"""
        if region == "all":
            await self.priceall(ctx)
            return
        try:
            api_client = await get_api_client(self.bot, ctx, region)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))
            return

        if region not in VALID_REGIONS and region != "all":
            await ctx.send(
                _("Invalid region. Valid regions are: `eu`, `us`, `kr`, 'cn' or `all`."),
                ephemeral=True,
            )
            return

        await ctx.defer()
        async with api_client as wow_client:
            wow_client = wow_client.Retail
            await self.limiter.acquire()
            wow_token = await wow_client.GameData.get_wow_token_index()
        token_price = wow_token["price"]

        gold_emotes = await self.config.emotes()
        message = _("Current price of the {region} WoW Token is: **{gold}**").format(
            region=region.upper(), gold=format_to_gold(token_price, gold_emotes)
        )

        embed = discord.Embed(description=message, colour=await ctx.embed_colour())
        await ctx.send(embed=embed)

    async def priceall(self, ctx):
        """Check price of the WoW token in all supported regions"""
        embed = discord.Embed(title=_("WoW Token prices"), colour=await ctx.embed_colour())

        await ctx.defer()
        for region in VALID_REGIONS:
            try:
                api_client = await get_api_client(self.bot, ctx, region)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))
                return
            async with api_client as wow_client:
                wow_client = wow_client.Retail
                await self.limiter.acquire()
                wow_token = await wow_client.GameData.get_wow_token_index()

            token_price = str(wow_token["price"])
            gold_emotes = await self.config.emotes()
            embed.add_field(
                name=region.upper(),
                value=format_to_gold(token_price, gold_emotes),
            )
        await ctx.send(embed=embed)
