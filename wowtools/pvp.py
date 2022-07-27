import functools

import discord
from blizzardapi import BlizzardApi
from redbot.core import commands
from redbot.core.i18n import Translator

from .utils import setup_pvp_functools

_ = Translator("WoWTools", __file__)


class PvP:
    @commands.command()
    async def rating(self, ctx, character_name: str, *realm: str):
        """Check a character's PVP ratings."""
        async with ctx.typing():
            blizzard_api = await self.bot.get_shared_api_tokens("blizzard")
            cid = blizzard_api.get("client_id")
            secret = blizzard_api.get("client_secret")

            if not cid or not secret:
                return await ctx.send(
                    _(
                        "The Blizzard API is not properly set up.\n"
                        "Create a client on https://develop.battle.net/ and then type in "
                        "`{prefix}set api blizzard client_id,whoops client_secret,whoops` "
                        "filling in `whoops` with your client's ID and secret."
                    ).format(prefix=ctx.prefix)
                )

            region = await self.config.guild(ctx.guild).region()
            realm = "-".join(realm).lower()
            character_name = character_name.lower()
            rbg_rating = "0"
            duo_rating = "0"
            tri_rating = "0"
            color = discord.Color.red()
            try:
                if realm == "":
                    raise ValueError(_("You didn't give me a realm."))
                api_client = BlizzardApi(cid, secret)
                fetch_profile = functools.partial(
                    api_client.wow.profile.get_character_profile_summary,
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                )
                fetch_achievements = functools.partial(
                    api_client.wow.profile.get_character_achievements_summary,
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                )
                fetch_media = functools.partial(
                    api_client.wow.profile.get_character_media_summary,
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                )
                (
                    fetch_duo_statistics,
                    fetch_rbg_statistics,
                    fetch_tri_statistics,
                ) = await setup_pvp_functools(api_client, character_name, realm, region)

                await self.limiter.acquire()
                profile = await self.bot.loop.run_in_executor(None, fetch_profile)

                await self.limiter.acquire()
                achievements = await self.bot.loop.run_in_executor(
                    None, fetch_achievements
                )

                await self.limiter.acquire()
                media = await self.bot.loop.run_in_executor(None, fetch_media)

                await self.limiter.acquire()
                rbg_statistics = await self.bot.loop.run_in_executor(
                    None, fetch_rbg_statistics
                )

                await self.limiter.acquire()
                duo_statistics = await self.bot.loop.run_in_executor(
                    None, fetch_duo_statistics
                )

                await self.limiter.acquire()
                tri_statistics = await self.bot.loop.run_in_executor(
                    None, fetch_tri_statistics
                )

                if "name" not in profile:
                    raise ValueError(_("That character or realm does not exist."))

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
                }
                own_season_achievements = {
                    "Season 1": {},
                    "Season 2": {},
                    "Season 3": {},
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
                ):
                    embed.add_field(
                        name=_("Achievements"), value="\n".join(achi_to_post)
                    )

                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))
