import discord

from redbot.core import commands
from redbot.core.i18n import Translator

from blizzardapi import BlizzardApi

_ = Translator("WoWTools", __file__)


class Wowpvp:
    """Cog for some pvp stuff"""

    @commands.command()
    async def rating(self, ctx, character_name: str, *realm: str):
        """Check a character's PVP ratings."""
        async with ctx.typing():
            blizzard_api = await self.bot.get_shared_api_tokens("blizzard")
            cid = blizzard_api.get("client_id")
            secret = blizzard_api.get("client_secret")

            if not cid or not secret:
                return await ctx.send(_("The Blizzard API is not properly set up."))

            region = await self.config.region()
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
                profile = api_client.wow.profile.get_character_profile_summary(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                )
                achievements = api_client.wow.profile.get_character_achievements_summary(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                )
                media = api_client.wow.profile.get_character_media_summary(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                )
                rbg_statistics = api_client.wow.profile.get_character_pvp_bracket_statistics(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                    pvp_bracket="rbg",
                )
                duo_statistics = api_client.wow.profile.get_character_pvp_bracket_statistics(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                    pvp_bracket="2v2",
                )
                tri_statistics = api_client.wow.profile.get_character_pvp_bracket_statistics(
                    region=region,
                    realm_slug=realm,
                    character_name=character_name,
                    locale="en_US",
                    pvp_bracket="3v3",
                )

                if "name" not in profile:
                    raise ValueError(_("That character or realm does not exist."))

                real_char_name: str = profile["name"]
                char_img_url: str = media["assets"][0]["value"]
                char_race: str = profile["race"]["name"]
                char_class: str = profile["character_class"]["name"]
                char_faction: str = profile["faction"]["name"]

                # TODO: Fetch current expansion seasons programmatically
                season_achievements = {  # Gladiator, Duelist, Rival, Challenger, Combatant
                    "Season 1": (14689, 14688, 14687, 14686, 14685),
                    "Season 2": (14972, 14971, 14970, 14969, 14968),
                }
                own_season_achievements = {"Season 1": {}, "Season 2": {}}
                for char_achievement in achievements["achievements"]:
                    for season in season_achievements.keys():
                        achi_id: int = char_achievement["id"]
                        if achi_id in season_achievements[season]:
                            own_season_achievements[season][achi_id] = char_achievement["achievement"]["name"]
                achi_to_post = []
                for season in own_season_achievements.keys():
                    if own_season_achievements[season] != {}:
                        achi_to_post.append(
                            own_season_achievements[season][max(own_season_achievements[season].keys())]
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
                if own_season_achievements["Season 1"] != {} or own_season_achievements["Season 2"] != {}:
                    embed.add_field(name=_("Achievements"), value="\n".join(achi_to_post))

                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))
