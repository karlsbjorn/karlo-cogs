import aiohttp
from datetime import timedelta
from dateutil.parser import isoparse

import discord

from redbot.core import commands
from redbot.core.i18n import Translator

_ = Translator("WoWTools", __file__)

RIO_URL = "https://raider.io/api/v1/"


class Raiderio:
    """Cog for interaction with the raider.io API"""

    @commands.command()
    async def profile(self, ctx, character: str, *realm: str) -> None:
        """Display the raider.io profile of a character."""
        async with ctx.typing():
            region = await self.config.region()
            realm = "-".join(realm).lower()
            request_url = f"{RIO_URL}characters/profile?region={region}&realm={realm}&name={character}&fields=mythic_plus_scores_by_season%3Acurrent%2Craid_progression%2Cgear%2Ccovenant"
            try:
                if realm == "":
                    raise ValueError(_("You didn't give me a realm."))
                async with self.session.request("GET", request_url) as resp:
                    profile_data = await resp.json()
                    if (
                        resp.status != 200
                        and profile_data["message"]
                        == "Could not find requested character"
                    ):
                        raise ValueError(_("That character does not exist."))

                    # TODO: Dict?
                    char_name = profile_data["name"]
                    char_race = profile_data["race"]
                    char_spec = profile_data["active_spec_name"]
                    char_class = profile_data["class"]
                    char_image = profile_data["thumbnail_url"]
                    char_score = profile_data["mythic_plus_scores_by_season"][0][
                        "segments"
                    ]["all"]
                    char_score_color = int("0x" + char_score["color"][1:], 0)
                    char_raid = profile_data["raid_progression"][
                        "sepulcher-of-the-first-ones"
                    ]["summary"]
                    char_last_updated = self._parse_date(
                        profile_data["last_crawled_at"]
                    )
                    char_ilvl = profile_data["gear"]["item_level_equipped"]
                    char_covenant = profile_data["covenant"]["name"]
                    char_url = profile_data["profile_url"]

                    banner = profile_data["profile_banner"]

                    banner_url = f"https://cdnassets.raider.io/images/profile/masthead_backdrops/v2/{banner}.jpg"
                    armory_url = f"https://worldofwarcraft.com/en-gb/character/eu/{realm}/{char_name}"
                    wcl_url = (
                        f"https://www.warcraftlogs.com/character/eu/{realm}/{char_name}"
                    )
                    raidbots_url = f"https://www.raidbots.com/simbot/quick?region=eu&realm={realm}&name={char_name}"

                    embed = discord.Embed(
                        title=char_name,
                        url=char_url,
                        description=f"{char_race} {char_spec} {char_class}",
                        color=char_score_color,
                    )
                    embed.set_author(
                        name=_("Raider.io profile"),
                        icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg",
                    )
                    embed.set_thumbnail(url=char_image)
                    embed.add_field(
                        name=_("__**Mythic+ Score**__"),
                        value=char_score["score"],
                        inline=False,
                    )
                    embed.add_field(
                        name=_("Raid progress"), value=char_raid, inline=True
                    )
                    embed.add_field(name=_("Item level"), value=char_ilvl, inline=True)
                    embed.add_field(
                        name=_("Covenant"), value=char_covenant, inline=True
                    )
                    embed.add_field(
                        name=_("__Other links__"),
                        value=_(
                            "[Armory]({armory_url}) | [WarcraftLogs]({wcl_url}) | [Raidbots]({raidbots_url})"
                        ).format(
                            armory_url=armory_url,
                            wcl_url=wcl_url,
                            raidbots_url=raidbots_url,
                        ),
                    )
                    embed.set_image(url=banner_url)
                    embed.set_footer(
                        text=_("Last updated: {char_last_updated}").format(
                            char_last_updated=char_last_updated
                        )
                    )

                    await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @commands.command()
    async def gprofile(self, ctx, *, guild: str = "Jahaci Rumene Kadulje") -> None:
        """Display the raider.io profile of a Ragnaros EU guild."""
        async with ctx.typing():
            region = await self.config.region()
            request_url = f"{RIO_URL}guilds/profile?region={region}&realm=Ragnaros&name={guild}&fields=raid_progression%2Craid_rankings"
            try:
                async with self.session.request("GET", request_url) as resp:
                    profile_data = await resp.json()
                    if (
                        resp.status != 200
                        and profile_data["message"] == "Could not find requested guild"
                    ):
                        raise ValueError(_("That guild does not exist on EU Ragnaros."))

                    guild_name: str = profile_data["name"]
                    guild_url: str = profile_data["profile_url"]
                    last_updated: str = self._parse_date(
                        profile_data["last_crawled_at"]
                    )

                    ranks = (
                        profile_data["raid_rankings"]["sepulcher-of-the-first-ones"][
                            "normal"
                        ],
                        profile_data["raid_rankings"]["sepulcher-of-the-first-ones"][
                            "heroic"
                        ],
                        profile_data["raid_rankings"]["sepulcher-of-the-first-ones"][
                            "mythic"
                        ],
                    )
                    difficulties = ("Normal", "Heroic", "Mythic")

                    raid_progression: str = profile_data["raid_progression"][
                        "sepulcher-of-the-first-ones"
                    ]["summary"]

                    embed = discord.Embed(
                        title=guild_name, url=guild_url, color=0xFF2121
                    )
                    embed.set_author(
                        name=_("Guild profile"),
                        icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg",
                    )
                    embed.add_field(
                        name=_("__**Progress**__"), value=raid_progression, inline=False
                    )

                    for rank, difficulty in zip(ranks, difficulties):
                        world = rank["world"]
                        region = rank["region"]
                        realm = rank["realm"]

                        embed.add_field(
                            name=_("{difficulty} rank").format(difficulty=difficulty),
                            value=_(
                                "World: {world}\nRegion: {region}\nRealm: {realm}"
                            ).format(world=world, region=region, realm=realm),
                        )

                    embed.set_footer(
                        text=_("Last updated: {last_updated}").format(
                            last_updated=last_updated
                        )
                    )

                    await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @staticmethod
    def _parse_date(tz_date) -> str:
        parsed = isoparse(tz_date) + timedelta(hours=2)
        formatted = parsed.strftime("%d/%m/%y - %H:%M:%S")
        return formatted

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
