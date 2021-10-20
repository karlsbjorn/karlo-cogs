import aiohttp
from datetime import timedelta
from dateutil.parser import isoparse
import discord
from redbot.core import commands

RIO_URL = "https://raider.io/api/v1/"


class Raiderio(commands.Cog):
    """Cog za"""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    @commands.command()
    async def profile(self, ctx, character: str) -> None:
        """Prikaži Raider.io profil nekog charactera iz Ragnaros-EU realma."""
        request_url = f"{RIO_URL}characters/profile?region=eu&realm=Ragnaros&name={character}&fields=mythic_plus_scores_by_season%3Acurrent%2Craid_progression%2Cgear%2Ccovenant"
        try:
            async with self.session.request("GET", request_url) as resp:
                assert resp.status == 200
                profile_data = await resp.json()

                char_name = profile_data["name"]
                char_race = profile_data["race"]
                char_spec = profile_data["active_spec_name"]
                char_class = profile_data["class"]
                char_image = profile_data["thumbnail_url"]
                char_score = profile_data["mythic_plus_scores_by_season"][0]["segments"]["all"]
                char_score_color = int("0x" + char_score["color"][1:], 0)
                char_raid = profile_data["raid_progression"]["sanctum-of-domination"]["summary"]
                char_last_updated = self._parse_date(profile_data["last_crawled_at"])
                char_ilvl = profile_data["gear"]["item_level_equipped"]
                char_covenant = profile_data["covenant"]["name"]
                char_url = profile_data["profile_url"]

                banner = profile_data["profile_banner"]

                banner_url = f"https://cdnassets.raider.io/images/profile/masthead_backdrops/v2/{banner}.jpg"
                armory_url = f"https://worldofwarcraft.com/en-gb/character/eu/ragnaros/{char_name}"
                wcl_url = f"https://www.warcraftlogs.com/character/eu/ragnaros/{char_name}"
                raidbots_url = f"https://www.raidbots.com/simbot/quick?region=eu&realm=ragnaros&name={char_name}"

                embed = discord.Embed(title=char_name,
                                      url=char_url,
                                      description=f"{char_race} {char_spec} {char_class}",
                                      color=char_score_color)
                embed.set_author(name="Raider.io profil",
                                 icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg")
                embed.set_thumbnail(url=char_image)
                embed.add_field(name="__**Mythic+ Score**__", value=char_score["score"], inline=False)
                embed.add_field(name="Raid progres", value=char_raid, inline=True)
                embed.add_field(name="Item level", value=char_ilvl, inline=True)
                embed.add_field(name="Covenant", value=char_covenant, inline=True)
                embed.add_field(name="__Ostali linkovi__", value=f"[Armory]({armory_url}) | [WarcraftLogs]({wcl_url}) | [Raidbots]({raidbots_url})")
                embed.set_image(url=banner_url)
                embed.set_footer(text=f"Posljedni put ažurirano: {char_last_updated}")

                await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Naredba uspješno neuspješna. {e}")

    @staticmethod
    def _parse_date(tz_date) -> str:
        parsed = isoparse(tz_date) + timedelta(hours=2)
        formatted = parsed.strftime("%d/%m/%y - %H:%M:%S")
        return formatted

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
