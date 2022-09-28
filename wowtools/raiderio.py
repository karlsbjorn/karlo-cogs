import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import discord
from aiowowapi import WowApi
from dateutil.parser import isoparse
from discord.embeds import EmptyEmbed
from raiderio_async import RaiderIO
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils import menus
from redbot.core.utils.chat_formatting import box, humanize_list
from redbot.core.utils.menus import DEFAULT_CONTROLS
from tabulate import tabulate

from wowtools.utils import get_api_client

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)


class Raiderio:
    """Cog for interaction with the raider.io API"""

    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    @commands.group(aliases=["rio"])
    async def raiderio(self, ctx: commands.Context):
        """Commands for interacting with Raider.io"""
        pass

    @raiderio.command(name="profile")
    @commands.guild_only()
    async def raiderio_profile(
        self, ctx, character: str = None, *, realm: str = None
    ) -> None:
        """Display the raider.io profile of a character.

        **Example:**
        [p]raiderio profile Karlo Ragnaros
        """
        async with ctx.typing():
            region: str = await self.config.guild(ctx.guild).region()
            armory_dict = await WowApi.parse_armory_link(character)
            if armory_dict:
                character = armory_dict["name"]
                realm = armory_dict["realm"]
                region = armory_dict["region"]
            if not character and not realm:
                region: str = await self.config.user(ctx.author).wow_character_region()
                if not region:
                    region: str = await self.config.guild(ctx.guild).region()
                    if not region:
                        await ctx.send_help()
                        return
            if not character:
                character: str = await self.config.user(ctx.author).wow_character_name()
                if not character:
                    await ctx.send_help()
                    return
            if not realm:
                realm: str = await self.config.user(ctx.author).wow_character_realm()
                if not realm:
                    await ctx.send_help()
                    return
            realm = (
                "-".join(realm).lower() if isinstance(realm, tuple) else realm.lower()
            )
            if realm == "":
                await ctx.send(_("You didn't give me a realm."))
                return

            async with RaiderIO() as rio:
                profile_data = await rio.get_character_profile(
                    region,
                    realm,
                    character,
                    fields=[
                        "mythic_plus_scores_by_season:current",
                        "raid_progression",
                        "gear",
                        "covenant",
                        "mythic_plus_best_runs",
                    ],
                )

                try:
                    char_name = profile_data["name"]
                except KeyError:
                    await ctx.send(_("Character not found."))
                    return
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
                char_last_updated = self._parse_date(profile_data["last_crawled_at"])
                char_ilvl = profile_data["gear"]["item_level_equipped"]
                try:
                    char_covenant = profile_data["covenant"]["name"]
                except TypeError:
                    char_covenant = "None"
                char_url = profile_data["profile_url"]

                banner = profile_data["profile_banner"]

                banner_url = f"https://cdnassets.raider.io/images/profile/masthead_backdrops/v2/{banner}.jpg"
                armory_url = f"https://worldofwarcraft.com/en-gb/character/{region}/{realm}/{char_name}"
                wcl_url = f"https://www.warcraftlogs.com/character/{region}/{realm}/{char_name}"
                raidbots_url = f"https://www.raidbots.com/simbot/quick?region={region}&realm={realm}&name={char_name}"

                embeds = []
                # First page
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
                embed.add_field(name=_("Raid progress"), value=char_raid, inline=True)
                embed.add_field(name=_("Item level"), value=char_ilvl, inline=True)
                embed.add_field(name=_("Covenant"), value=char_covenant, inline=True)
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
                embeds.append(embed)

                # Second page
                dungeon_str = _("Dungeon")
                key_level_str = _("Level")
                runs = {
                    dungeon_str: [],
                    key_level_str: [],
                }
                best_runs: List[Dict] = profile_data["mythic_plus_best_runs"]
                for run in best_runs:
                    dungeon_short = run["short_name"]
                    key_level = run["mythic_level"]
                    runs[dungeon_str] += [dungeon_short]
                    runs[key_level_str] += [f"+{key_level}"]
                if not runs[dungeon_str]:
                    # If no runs in current season, send basic profile embed
                    await ctx.send(embed=embed)
                    return
                tabulated = tabulate(
                    runs, headers="keys", tablefmt="simple", colalign=("left", "right")
                )

                embed = discord.Embed(
                    title=char_name,
                    description=box(
                        tabulated,
                    ),
                    url=char_url,
                    color=char_score_color,
                )
                embed.set_author(
                    name=_("Raider.io profile"),
                    icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg",
                )
                embed.set_thumbnail(url=char_image)
                embed.set_footer(
                    text=_("Last updated: {char_last_updated}").format(
                        char_last_updated=char_last_updated
                    )
                )
                embeds.append(embed)

        await menus.menu(ctx, pages=embeds, controls=DEFAULT_CONTROLS)

    @raiderio.command(name="guild")
    @commands.guild_only()
    async def raiderio_guild(
        self, ctx: commands.Context, guild: str, *realm: str
    ) -> None:
        """Display the raider.io profile of a guild.

        If the guild or realm name have spaces in them, they need to be enclosed in quotes.

        Example:
        [p]raiderio guild "Jahaci Rumene Kadulje" Ragnaros
        """
        async with ctx.typing():
            region: str = await self.config.guild(ctx.guild).region()
            if not realm:
                realm: str = await self.config.guild(ctx.guild).realm()
            if not region:
                await ctx.send(
                    _(
                        "A server admin needs to set a region with `{prefix}wowset region` first."
                    ).format(prefix=ctx.clean_prefix)
                )
                return
            if not realm:
                await ctx.send(
                    _(
                        "A server admin needs to set a realm with `{prefix}wowset realm` first."
                    ).format(prefix=ctx.clean_prefix)
                )
                return
            async with RaiderIO() as rio:
                profile_data = await rio.get_guild_profile(
                    region,
                    realm,
                    guild,
                    fields=["raid_rankings", "raid_progression"],
                )

                try:
                    guild_name: str = profile_data["name"]
                except KeyError:
                    await ctx.send(
                        _("The guild {guild} does not exist on {realm}.").format(
                            guild=guild, realm=realm[0]
                        )
                    )
                    return
                guild_url: str = profile_data["profile_url"]
                last_updated: str = self._parse_date(profile_data["last_crawled_at"])

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

                embed = discord.Embed(title=guild_name, url=guild_url, color=0xFF2121)
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

    @raiderio.command(name="affixes")
    @commands.guild_only()
    async def raiderio_affixes(self, ctx: commands.Context, region: str = None) -> None:
        """Display this week's affixes."""
        async with ctx.typing():
            if not region:
                region: str = await self.config.guild(ctx.guild).region()
                if not region:
                    await ctx.send_help()
                    return
            regions = ("us", "eu", "kr", "cn")
            if region.lower() not in regions:
                await ctx.send(
                    _("Region must be one of the following: {regions}").format(
                        regions=humanize_list(regions, style="or")
                    )
                )
                return
            async with RaiderIO() as rio:
                affixes = await rio.get_mythic_plus_affixes(region)
                affixes = affixes["affix_details"]

            msg = ""
            if region == "eu":
                reset_day = 2  # Wednesday
                now = datetime.utcnow()
                reset_date = now + timedelta(days=(reset_day - now.weekday()) % 7)
                if now.date() == reset_date.date() and now.hour > 7:
                    reset_date += timedelta(days=7)
                reset_date = reset_date.replace(
                    hour=7, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
                )
                msg += _("\nThe weekly reset is {timestamp}.").format(
                    timestamp=f"<t:{int(reset_date.timestamp())}:R>"
                )
            elif region == "us":
                reset_day = 1  # Tuesday
                now = datetime.utcnow()
                reset_date = now + timedelta(days=(reset_day - now.weekday()) % 7)
                if now.date() == reset_date.date() and now.hour > 15:
                    reset_date += timedelta(days=7)
                reset_date = reset_date.replace(
                    hour=15, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
                )
                msg += _("\nThe weekly reset is {timestamp}.").format(
                    timestamp=f"<t:{int(reset_date.timestamp())}:R>"
                )
            # TODO: Find out when the reset is for KR and CN
            embed = discord.Embed(
                title=_("This week's Mythic+ affixes"),
                description=msg if msg else EmptyEmbed,
                color=await ctx.embed_color(),
            )
            embed.set_thumbnail(url="https://i.imgur.com/kczQ4Jt.jpg")
            for affix in affixes:
                embed.add_field(
                    name=affix["name"],
                    value=affix["description"],
                    inline=False,
                )
        await ctx.send(embed=embed)

    @staticmethod
    def _parse_date(tz_date) -> str:
        parsed = isoparse(tz_date) + timedelta(hours=2)
        formatted = parsed.strftime("%d/%m/%y - %H:%M:%S")
        return formatted
