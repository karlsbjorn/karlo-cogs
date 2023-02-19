from typing import List, Optional

import discord
from aiohttp import ClientResponseError
from aiowowapi import RetailApi
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, set_contextual_locales_from_guild

from .utils import get_api_client, get_realms

_ = Translator("WoWTools", __file__)


class PvP:
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    @commands.hybrid_command()
    async def rating(self, ctx, character: str, *, realm: str):
        """Check a character's PVP ratings."""
        if ctx.interaction:
            # There is no contextual locale for interactions, so we need to set it manually
            # (This is probably a bug in Red, remove this when it's fixed)
            await set_contextual_locales_from_guild(self.bot, ctx.guild)

        realm, region = realm.split(sep=":")
        region = region.lower()
        try:
            api_client = await get_api_client(self.bot, ctx, region)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))
            return
        realm = await api_client.get_realm_slug(realm)

        rbg_rating = "0"
        duo_rating = "0"
        tri_rating = "0"

        await ctx.defer()
        async with api_client:
            wow_client = api_client.Retail
            try:
                await self.limiter.acquire()
                profile = await wow_client.Profile.get_character_profile_summary(
                    character_name=character, realm_slug=realm
                )
            except ClientResponseError:
                await ctx.send(
                    _('Character "{character_name}" not found.').format(character_name=character)
                )
                return

            await self.limiter.acquire()
            achievements = await wow_client.Profile.get_character_achievements_summary(
                character_name=character, realm_slug=realm
            )

            await self.limiter.acquire()
            media = await wow_client.Profile.get_character_media_summary(
                character_name=character, realm_slug=realm
            )

            try:
                await self.limiter.acquire()
                rbg_statistics = await wow_client.Profile.get_character_pvp_bracket_statistics(
                    character_name=character,
                    realm_slug=realm,
                    pvp_bracket="rbg",
                )
            except ClientResponseError:
                rbg_statistics = {}
            try:
                await self.limiter.acquire()
                duo_statistics = await wow_client.Profile.get_character_pvp_bracket_statistics(
                    character_name=character,
                    realm_slug=realm,
                    pvp_bracket="2v2",
                )
            except ClientResponseError:
                duo_statistics = {}
            try:
                await self.limiter.acquire()
                tri_statistics = await wow_client.Profile.get_character_pvp_bracket_statistics(
                    character_name=character,
                    realm_slug=realm,
                    pvp_bracket="3v3",
                )
            except ClientResponseError:
                tri_statistics = {}
            try:
                await self.limiter.acquire()
                shuffle_rating = await self.get_shuffle_rating(wow_client, profile)
            except ClientResponseError:
                shuffle_rating = None

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
            # Shadowlands
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
            # Dragonflight
            "Season 1": (
                15958,
                15959,
                15951,
                15984,
                15954,
                15952,
                15953,
                15955,
                15956,
                15960,
                15961,
            ),
        }
        own_season_achievements = {
            "Season 2": {},
            "Season 3": {},
            "Season 4": {},
            "Season 1": {},
        }
        for char_achievement in achievements["achievements"]:
            achi_id: int = char_achievement["id"]
            for season, value_ in season_achievements.items():
                if achi_id in value_:
                    own_season_achievements[season][achi_id] = char_achievement["achievement"][
                        "name"
                    ]
        achi_to_post = [
            own_season_achievements[season][max(own_season_achievements[season].keys())]
            for season, value__ in own_season_achievements.items()
            if value__ != {}
        ]
        if char_faction != "Horde":
            color = discord.Color.blue()
        else:
            color = discord.Color.red()

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
        embed.add_field(
            name=_("Solo Shuffle Rating"),
            value=shuffle_rating or _("Character not on the leaderboard"),
            inline=False,
        )
        if (
            own_season_achievements["Season 1"] != {}
            or own_season_achievements["Season 2"] != {}
            or own_season_achievements["Season 3"] != {}
            or own_season_achievements["Season 4"] != {}
        ):
            embed.add_field(name=_("Achievements"), value="\n".join(achi_to_post))

        details_url = (
            f"https://check-pvp.fr/"
            f"{region}/"
            f"{realm.capitalize()}/"
            f"{character.capitalize()}"
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label=_("More details"), style=discord.ButtonStyle.link, url=details_url
            )
        )

        await ctx.send(embed=embed, view=view)

    @rating.autocomplete("realm")
    async def rating_realm_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        realms = await get_realms(current)
        return realms[:25]

    @staticmethod
    async def get_shuffle_rating(wow_client: RetailApi, profile) -> Optional[int]:
        char_class: str = profile["character_class"]["name"]
        char_class = char_class.lower().replace(" ", "")

        char_spec: str = profile["active_spec"]["name"]
        char_spec = char_spec.lower().replace(" ", "")

        pvp_bracket = f"shuffle-{char_class}-{char_spec}"
        leaderboard = await wow_client.GameData.get_pvp_leaderboard(
            pvp_season_id=34,
            pvp_bracket=pvp_bracket,
        )
        return next(
            (
                entry["rating"]
                for entry in leaderboard["entries"]
                if entry["character"]["name"] == profile["name"]
            ),
            None,
        )
