import discord
from redbot.core import Config
from redbot.core import commands
from blizzardapi import BlizzardApi


class Wowpvp(commands.Cog):
    """Cog za neke pvp stvari"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=4207)
        default_global = {
            "client_id": "1234",
            "client_secret": "5678",
            "region": "eu"
        }
        self.config.register_global(**default_global)

    @commands.command()
    async def rating(self, ctx, character_name: str, *realm: str):
        """Provjeri rejtinge nekog charactera"""
        async with ctx.typing():
            region = await self.config.region()
            realm = '-'.join(realm).lower()
            character_name = character_name.lower()
            rbg_rating = "0"
            duo_rating = "0"
            tri_rating = "0"
            color = discord.Color.red()
            try:
                api_client = BlizzardApi(await self.config.client_id(), await self.config.client_secret())
                profile = api_client.wow.profile.get_character_profile_summary(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US"
                )
                media = api_client.wow.profile.get_character_media_summary(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US"
                )
                rbg_statistics = api_client.wow.profile.get_character_pvp_bracket_statistics(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                    pvp_bracket="rbg"
                )
                duo_statistics = api_client.wow.profile.get_character_pvp_bracket_statistics(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                    pvp_bracket="2v2"
                )
                tri_statistics = api_client.wow.profile.get_character_pvp_bracket_statistics(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                    pvp_bracket="3v3"
                )

                if "name" not in profile:
                    raise ValueError("Taj character ne postoji.")

                real_char_name: str = profile["name"]
                char_img_url: str = media["assets"][0]["value"]
                char_race: str = profile["race"]["name"]
                char_class: str = profile["character_class"]["name"]
                char_faction: str = profile["faction"]["name"]

                if char_faction != "Horde":
                    color = discord.Color.blue()

                if "rating" in rbg_statistics:
                    rbg_rating: str = rbg_statistics["rating"]
                if "rating" in duo_statistics:
                    duo_rating: str = duo_statistics["rating"]
                if "rating" in tri_statistics:
                    tri_rating: str = tri_statistics["rating"]

                embed = discord.Embed(
                    color=color,
                    title=real_char_name,
                    description=f"{char_race} {char_class}"
                )
                embed.set_thumbnail(
                    url=char_img_url
                )
                embed.add_field(
                    name="RBG Rating",
                    value=rbg_rating
                )
                embed.add_field(
                    name="2v2 Rating",
                    value=duo_rating
                )
                embed.add_field(
                    name="3v3 Rating",
                    value=tri_rating
                )
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f"Naredba uspješno neuspješna. {e}")

    @commands.group()
    async def pvpset(self, ctx):
        """Postavke coga"""
        pass

    @pvpset.command()
    @commands.is_owner()
    async def api(self, ctx, client_id: str, client_secret: str):
        """Postavi Blizzard API"""
        async with ctx.typing():
            try:
                await self.config.client_id.set(client_id)
                await self.config.client_secret.set(client_secret)
                await ctx.send("**Client ID** i **Client Secret** uspješno postavljeni.")
            except Exception as e:
                await ctx.send(e)

    @pvpset.command()
    @commands.is_owner()
    async def region(self, ctx, region: str):
        """
        Postavi regiju gdje će se characteri pretraživat.

        Regije: us, eu, kr, tw, cn
        """
        regions = ("us", "eu", "kr", "tw", "cn")
        async with ctx.typing():
            try:
                if region not in regions:
                    raise ValueError("Ta regija ne postoji.\n\nDozvoljene regije su: us, eu, kr, tw, cn")
                await self.config.region.set(region)
                await ctx.send("Regija uspješno postavljena.")
            except Exception as e:
                await ctx.send(e)
