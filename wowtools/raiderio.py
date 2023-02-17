import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import discord
from dateutil.parser import isoparse
from raiderio_async import RaiderIO
from redbot.core import commands
from redbot.core.i18n import Translator, set_contextual_locales_from_guild
from redbot.core.utils.chat_formatting import box, humanize_list
from redbot.core.utils.views import _ACCEPTABLE_PAGE_TYPES, SimpleMenu
from tabulate import tabulate

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)


class Raiderio:
    """Cog for interaction with the raider.io API"""

    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    @commands.hybrid_group(aliases=["rio"])
    async def raiderio(self, ctx: commands.Context):
        """Commands for interacting with Raider.io"""
        pass

    @raiderio.command(name="profile")
    @commands.guild_only()
    async def raiderio_profile(self, ctx, character: str, *, realm: str, region: str) -> None:
        """Display the raider.io profile of a character.

        **Example:**
        [p]raiderio profile Karlo Ragnaros
        """
        if ctx.interaction:
            # There is no contextual locale for interactions, so we need to set it manually
            # (This is probably a bug in Red, remove this when it's fixed)
            await set_contextual_locales_from_guild(self.bot, ctx.guild)

        realm = ("-".join(realm).lower() if isinstance(realm, tuple) else realm.lower()).replace(
            " ", "-"
        )
        region = region.lower()
        if ctx.interaction:
            await ctx.defer()
        async with RaiderIO() as rio:
            profile_data = await rio.get_character_profile(
                region,
                realm,
                character,
                fields=[
                    "mythic_plus_scores_by_season:current",
                    "raid_progression",
                    "gear",
                    "mythic_plus_best_runs",
                    "talents",
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
        char_score = profile_data["mythic_plus_scores_by_season"][0]["segments"]["all"]
        char_score_color = int("0x" + char_score["color"][1:], 0)
        char_raid = profile_data["raid_progression"]["vault-of-the-incarnates"]["summary"]
        char_last_updated = self._parse_date(profile_data["last_crawled_at"])
        char_gear = profile_data["gear"]
        char_ilvl = char_gear["item_level_equipped"]
        char_url = profile_data["profile_url"]
        char_talents = profile_data["talentLoadout"]["loadout_text"]

        banner = profile_data["profile_banner"]

        banner_url = (
            f"https://cdnassets.raider.io/images/profile/masthead_backdrops/v2/{banner}.jpg"
        )
        armory_url = f"https://worldofwarcraft.com/en-gb/character/{region}/{realm}/{char_name}"
        wcl_url = f"https://www.warcraftlogs.com/character/{region}/{realm}/{char_name}"
        raidbots_url = (
            f"https://www.raidbots.com/simbot/quick?region={region}&realm={realm}&name={char_name}"
        )

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
        embed.add_field(
            name=_("__Other links__"),
            value=_(
                "[Armory]({armory_url}) | [WarcraftLogs]({wcl_url}) | [Raidbots]({raidbots_url})"
            ).format(
                armory_url=armory_url,
                wcl_url=wcl_url,
                raidbots_url=raidbots_url,
            ),
            inline=False,
        )
        embed.set_image(url=banner_url)
        embed.set_footer(
            text=_("Last updated: {char_last_updated}").format(char_last_updated=char_last_updated)
        )
        embeds = [embed]
        # Dungeon specifics page
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
        if runs[dungeon_str]:
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

        # Gear page
        embed = await self._make_gear_embed(
            char_gear, char_image, char_last_updated, char_name, char_score_color
        )
        embeds.append(embed)

        await ProfileMenu(pages=embeds, talents=char_talents, disable_after_timeout=True).start(
            ctx
        )

    @raiderio.command(name="guild")
    @commands.guild_only()
    async def raiderio_guild(self, ctx: commands.Context, guild: str, *, realm: str) -> None:
        """Display the raider.io profile of a guild.

        If the guild or realm name have spaces in them, they need to be enclosed in quotes.

        Example:
        [p]raiderio guild "Jahaci Rumene Kadulje" Ragnaros
        """
        if ctx.interaction:
            # There is no contextual locale for interactions, so we need to set it manually
            # (This is probably a bug in Red, remove this when it's fixed)
            await set_contextual_locales_from_guild(self.bot, ctx.guild)

        region: str = await self.config.guild(ctx.guild).region()
        if not realm:
            realm: str = await self.config.guild(ctx.guild).realm()
        if not region:
            await ctx.send(
                _(
                    "A server admin needs to set a region with `{prefix}wowset region` first."
                ).format(prefix="" if ctx.interaction else ctx.clean_prefix),
                ephemeral=True,
            )
            return
        if not realm:
            await ctx.send(
                _("A server admin needs to set a realm with `{prefix}wowset realm` first.").format(
                    prefix="" if ctx.interaction else ctx.clean_prefix
                ),
                ephemeral=True,
            )
            return

        await ctx.defer()
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
                profile_data["raid_rankings"]["sepulcher-of-the-first-ones"]["normal"],
                profile_data["raid_rankings"]["sepulcher-of-the-first-ones"]["heroic"],
                profile_data["raid_rankings"]["sepulcher-of-the-first-ones"]["mythic"],
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
            embed.add_field(name=_("__**Progress**__"), value=raid_progression, inline=False)

            for rank, difficulty in zip(ranks, difficulties):
                world = rank["world"]
                region = rank["region"]
                realm = rank["realm"]

                embed.add_field(
                    name=_("{difficulty} rank").format(difficulty=difficulty),
                    value=_("World: {world}\nRegion: {region}\nRealm: {realm}").format(
                        world=world, region=region, realm=realm
                    ),
                )

            embed.set_footer(
                text=_("Last updated: {last_updated}").format(last_updated=last_updated)
            )

        await ctx.send(embed=embed)

    @raiderio.command(name="affixes")
    @commands.guild_only()
    async def raiderio_affixes(self, ctx: commands.Context, region: str = None) -> None:
        """Display this week's affixes."""
        if ctx.interaction:
            # There is no contextual locale for interactions, so we need to set it manually
            # (This is probably a bug in Red, remove this when it's fixed)
            await set_contextual_locales_from_guild(self.bot, ctx.guild)

        if not region:
            region: str = await self.config.guild(ctx.guild).region()
        if not region:
            await ctx.send_help()
            return
        regions = ("us", "eu", "kr", "cn")
        if region.lower() not in regions:
            await ctx.send(
                _("Region must be one of the following: {regions}").format(
                    regions=humanize_list(regions, style="or"), ephemeral=True
                )
            )
            return

        await ctx.defer()
        async with RaiderIO() as rio:
            affixes = await rio.get_mythic_plus_affixes(region)
            affixes = affixes["affix_details"]

        msg = ""
        if region == "eu":
            now = datetime.now(timezone.utc)
            reset_date = now + timedelta(days=(2 - now.weekday()) % 7)
            if now.date() == reset_date.date() and now.hour > 7:
                reset_date += timedelta(days=7)
            reset_date = reset_date.replace(
                hour=7, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
            )
            msg += _("\nThe weekly reset is {timestamp}.").format(
                timestamp=f"<t:{int(reset_date.timestamp())}:R>"
            )
        elif region == "us":
            now = datetime.now(timezone.utc)
            reset_date = now + timedelta(days=(1 - now.weekday()) % 7)
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
            description=msg or None,
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
        return parsed.strftime("%d/%m/%y - %H:%M:%S")

    async def _make_gear_embed(
        self, char_gear, char_image, char_last_updated, char_name, char_score_color
    ):
        item_list = [
            _("**Average ilvl:** {avg_ilvl}\n").format(avg_ilvl=char_gear["item_level_equipped"])
        ]

        items = char_gear["items"]
        for item_slot, item in items.items():
            item_str = ""

            # Item rarity
            item_str += await self._get_item_quality(item)

            # Item level
            item_str += f" `{item['item_level']}`"

            # Item name
            item_name = item["name"]
            item_str += f" [{item_name}]"

            # Item link
            item_id = item["item_id"]
            item_str += f"({self._wowhead_url(item_id)})"

            item_list.append(item_str)

        embed = discord.Embed(
            title=char_name,
            description="\n".join(item_list),
            color=char_score_color,
        )
        embed.set_author(
            name=_("Raider.io profile"),
            icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg",
        )
        embed.set_thumbnail(url=char_image)
        embed.set_footer(
            text=_("Last updated: {char_last_updated}").format(char_last_updated=char_last_updated)
        )
        return embed

    @staticmethod
    async def _get_item_quality(item) -> str:
        """
        Get the item quality emoji.

        :param item: The item to get the quality emoji for.
        :return: The item quality emoji.
        """
        quality = item["item_quality"]
        if quality == 1:
            return "⬜"
        elif quality == 2:
            return "🟩"
        elif quality == 3:
            return "🟦"
        elif quality == 4:
            return "🟪"
        elif quality == 5:
            return "🟧"
        else:
            return "⬛"

    @staticmethod
    def _wowhead_url(item_id):
        """
        Returns a Wowhead URL for the given item ID.

        :param item_id: ID of the item
        :return: Wowhead URL
        """
        return f"https://www.wowhead.com/item={item_id}"


class ProfileMenu(SimpleMenu):
    def __init__(
        self,
        pages: List[_ACCEPTABLE_PAGE_TYPES],
        talents: str,
        timeout: float = 180.0,
        page_start: int = 0,
        delete_after_timeout: bool = False,
        disable_after_timeout: bool = False,
        use_select_menu: bool = False,
        use_select_only: bool = False,
    ) -> None:
        super().__init__(
            pages,
            timeout=timeout,
            page_start=page_start,
            delete_after_timeout=delete_after_timeout,
            disable_after_timeout=disable_after_timeout,
            use_select_menu=use_select_menu,
            use_select_only=use_select_only,
        )
        self.talents = talents
        self.import_talents.label = _("Import talents")

    @discord.ui.button(style=discord.ButtonStyle.green, row=1)
    async def import_talents(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            _(
                "Here are the talents this character's using:\n"
                "`{talents}`\n\n"
                "Import this text using the in-game talent import feature."
            ).format(talents=self.talents),
            ephemeral=True,
        )
