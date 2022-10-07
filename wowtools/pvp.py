import discord
from aiohttp import ClientResponseError
from aiowowapi import WowApi
from redbot.core import commands
from redbot.core.i18n import Translator

from .utils import get_api_client

_ = Translator("WoWTools", __file__)


class PvP:
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    @commands.command()
    async def rating(self, ctx, character_name: str = None, *, realm: str = None):
        """Check a character's PVP ratings."""
        async with ctx.typing():
            region: str = await self.config.guild(ctx.guild).region()
            armory_dict = await WowApi.parse_armory_link(character_name)
            if armory_dict:
                character_name = armory_dict["name"]
                realm = armory_dict["realm"]
                region = armory_dict["region"]
            if not character_name and not realm:
                region: str = await self.config.user(ctx.author).wow_character_region()
                if not region:
                    region: str = await self.config.guild(ctx.guild).region()
                    if not region:
                        await ctx.send_help()
                        return
            if not character_name:
                character_name: str = await self.config.user(
                    ctx.author
                ).wow_character_name()
                if not character_name:
                    await ctx.send_help()
                    return
            if not realm:
                realm: str = await self.config.user(ctx.author).wow_character_realm()
                if not realm:
                    await ctx.send_help()
                    return
            try:
                api_client = await get_api_client(self.bot, ctx, region)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))
                return
            realm = await api_client.get_realm_slug(realm)

            rbg_rating = "0"
            duo_rating = "0"
            tri_rating = "0"
            color = discord.Color.red()

            async with api_client:
                wow_client = api_client.Retail
                try:
                    await self.limiter.acquire()
                    profile = await wow_client.Profile.get_character_profile_summary(
                        character_name=character_name, realm_slug=realm
                    )
                except ClientResponseError:
                    await ctx.send(
                        _('Character "{character_name}" not found.').format(
                            character_name=character_name
                        )
                    )
                    return

                await self.limiter.acquire()
                achievements = (
                    await wow_client.Profile.get_character_achievements_summary(
                        character_name=character_name, realm_slug=realm
                    )
                )

                await self.limiter.acquire()
                media = await wow_client.Profile.get_character_media_summary(
                    character_name=character_name, realm_slug=realm
                )

                try:
                    await self.limiter.acquire()
                    rbg_statistics = (
                        await wow_client.Profile.get_character_pvp_bracket_statistics(
                            character_name=character_name,
                            realm_slug=realm,
                            pvp_bracket="rbg",
                        )
                    )
                except ClientResponseError:
                    rbg_statistics = {}
                try:
                    await self.limiter.acquire()
                    duo_statistics = (
                        await wow_client.Profile.get_character_pvp_bracket_statistics(
                            character_name=character_name,
                            realm_slug=realm,
                            pvp_bracket="2v2",
                        )
                    )
                except ClientResponseError:
                    duo_statistics = {}
                try:
                    await self.limiter.acquire()
                    tri_statistics = (
                        await wow_client.Profile.get_character_pvp_bracket_statistics(
                            character_name=character_name,
                            realm_slug=realm,
                            pvp_bracket="3v3",
                        )
                    )
                except ClientResponseError:
                    tri_statistics = {}

            if "name" not in profile:
                await ctx.send(_("That character or realm does not exist."))
                return

            real_char_name: str = profile["name"]
            char_img_url: str = media["assets"][0]["value"]
            char_race: str = profile["race"]["name"]
            char_class: str = profile["character_class"]["name"]
            char_faction: str = profile["faction"]["name"]

            # TODO: Fetch current expansion seasons programmatically
            season_achievements = {
                # Hero of the Horde, Hero of the Alliance, Gladiator, Elite, Duelist, Rival, Challenger, Combatant
                "Season 1": (
                    14693,
                    14692,
                    14689,
                    14691,
                    14688,
                    14687,
                    14686,
                    14685,
                ),
                "Season 2": (
                    14976,
                    14975,
                    14972,
                    14974,
                    14971,
                    14970,
                    14969,
                    14968,
                ),
                "Season 3": (
                    15356,
                    15355,
                    15352,
                    15354,
                    15351,
                    15350,
                    15349,
                    15348,
                ),
                "Season 4": (
                    15607,
                    15608,
                    15605,
                    15639,
                    15604,
                    15603,
                    15602,
                    15601,
                    15600,
                    15610,
                    15609,
                ),
            }
            own_season_achievements = {
                "Season 1": {},
                "Season 2": {},
                "Season 3": {},
                "Season 4": {},
            }
            for char_achievement in achievements["achievements"]:
                for season in season_achievements.keys():
                    achi_id: int = char_achievement["id"]
                    if achi_id in season_achievements[season]:
                        own_season_achievements[season][achi_id] = char_achievement[
                            "achievement"
                        ]["name"]
            achi_to_post = []
            for season in own_season_achievements.keys():
                if own_season_achievements[season] != {}:
                    achi_to_post.append(
                        own_season_achievements[season][
                            max(own_season_achievements[season].keys())
                        ]
                    )

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
                description=f"{char_race} {char_class}",
                url=f"https://worldofwarcraft.com/en-gb/character/{region}/{realm}/{real_char_name}",
            )
            embed.set_thumbnail(url=char_img_url)
            embed.add_field(name=_("RBG Rating"), value=rbg_rating)
            embed.add_field(name=_("2v2 Rating"), value=duo_rating)
            embed.add_field(name=_("3v3 Rating"), value=tri_rating)
            if (
                own_season_achievements["Season 1"] != {}
                or own_season_achievements["Season 2"] != {}
                or own_season_achievements["Season 3"] != {}
                or own_season_achievements["Season 4"] != {}
            ):
                embed.add_field(name=_("Achievements"), value="\n".join(achi_to_post))

        await ctx.send(embed=embed)
