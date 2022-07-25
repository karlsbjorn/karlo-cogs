import functools
import logging

import discord
from aiolimiter import AsyncLimiter
from blizzardapi import BlizzardApi
from discord.ext import tasks
from raiderio_async import RaiderIO
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number
from tabulate import tabulate

from .utils import get_api_client

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)


class Scoreboard:
    @commands.group(name="wowscoreboard", aliases=["sb"])
    @commands.guild_only()
    async def wowscoreboard(self, ctx: commands.Context):
        """Show various scoreboards for your guild."""
        pass

    @wowscoreboard.command(name="dungeon")
    @commands.guild_only()
    async def wowscoreboard_dungeon(self, ctx: commands.Context):
        """Get the Mythic+ scoreboard for this guild."""
        async with ctx.typing():
            embed = await self._generate_dungeon_scoreboard(ctx)
        if embed:
            await ctx.send(embed=embed)

    @wowscoreboard.command(name="pvp")
    @commands.guild_only()
    async def wowscoreboard_pvp(self, ctx: commands.Context):
        """Get all the PvP related scoreboards for this guild."""
        async with ctx.typing():
            embed = await self._generate_pvp_scoreboard(ctx)
        if embed:
            # TODO: In dpy2, make this a list of embeds to send in a single message
            await ctx.send(embed=embed)

    @commands.group()
    @commands.admin()
    @commands.guild_only()
    async def sbset(self, ctx):
        """Change scoreboard settings"""
        pass

    @sbset.command(name="channel")
    @commands.admin()
    @commands.guild_only()
    async def sbset_channel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Set the channel to send the scoreboard to."""
        sb_channel_id: int = await self.config.guild(ctx.guild).scoreboard_channel()
        sb_msg_id: int = await self.config.guild(ctx.guild).scoreboard_message()
        if not channel:
            if sb_msg_id:  # Remove the scoreboard message if it exists
                await self._delete_scoreboard(
                    ctx,
                    sb_channel_id,
                    sb_msg_id,
                )
            await self.config.guild(ctx.guild).scoreboard_channel.clear()
            await self.config.guild(ctx.guild).scoreboard_message.clear()
            await ctx.send(_("Scoreboard channel cleared."))
            return
        if sb_msg_id:  # Remove the old scoreboard
            await self._delete_scoreboard(
                ctx,
                sb_channel_id,
                sb_msg_id,
            )
        await self.config.guild(ctx.guild).scoreboard_channel.set(channel.id)
        embed = await self._generate_dungeon_scoreboard(ctx)
        sb_msg = await channel.send(embed=embed)
        await self.config.guild(ctx.guild).scoreboard_message.set(sb_msg.id)
        await ctx.send(_("Scoreboard channel set."))

    @sbset.group(name="blacklist", aliases=["blocklist"])
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist(self, ctx: commands.Context):
        """Manage the scoreboard blacklist."""
        pass

    @sbset_blacklist.command(name="add")
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist_add(self, ctx: commands.Context, *, characters: str):
        """Add characters to the scoreboard blacklist.

        Characters can be separated by spaces or commas.
        """
        blacklist: list[str] = await self.config.guild(ctx.guild).scoreboard_blacklist()
        for character in characters.split(" "):
            character = character.strip(",")
            if character not in blacklist:
                blacklist.append(character.lower())
        await self.config.guild(ctx.guild).scoreboard_blacklist.set(blacklist)
        await ctx.send(_("Blacklisted characters added."))

    @sbset_blacklist.command(name="remove")
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist_remove(self, ctx: commands.Context, *, characters: str):
        """Remove characters from the scoreboard blacklist.

        Characters can be separated by spaces or commas.
        """
        blacklist: list[str] = await self.config.guild(ctx.guild).scoreboard_blacklist()
        for character in characters.split(" "):
            character = character.strip(",")
            if character in blacklist:
                blacklist.remove(character.lower())
        await self.config.guild(ctx.guild).scoreboard_blacklist.set(blacklist)
        await ctx.send(_("Blacklisted characters removed."))

    @sbset_blacklist.command(name="list")
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist_list(self, ctx: commands.Context):
        """List the characters on the scoreboard blacklist."""
        blacklist: list[str] = await self.config.guild(ctx.guild).scoreboard_blacklist()
        if not blacklist:
            await ctx.send(_("No characters are blacklisted."))
            return
        await ctx.send(
            _("Blacklisted characters: {characters}").format(
                characters=humanize_list(blacklist)
            )
        )

    @sbset_blacklist.command(name="clear")
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist_clear(self, ctx: commands.Context):
        """Clear the scoreboard blacklist."""
        await self.config.guild(ctx.guild).scoreboard_blacklist.clear()
        await ctx.send(_("Blacklisted characters cleared."))

    @tasks.loop(minutes=5)
    async def update_dungeon_scoreboard(self):
        for guild in self.bot.guilds:
            if self.bot.cog_disabled_in_guild():
                continue
            sb_channel_id: int = await self.config.guild(guild).scoreboard_channel()
            sb_msg_id: int = await self.config.guild(guild).scoreboard_message()
            if sb_channel_id and sb_msg_id:
                sb_channel: discord.TextChannel = guild.get_channel(sb_channel_id)
                sb_msg: discord.Message = await sb_channel.fetch_message(sb_msg_id)
                if sb_msg:
                    max_chars = 20
                    headers = ["#", _("Name"), _("Score")]
                    region: str = await self.config.guild(guild).region()
                    realm: str = await self.config.guild(guild).realm()
                    guild_name: str = await self.config.guild(guild).real_guild_name()
                    sb_blacklist: list[str] = await self.config.guild(
                        guild
                    ).scoreboard_blacklist()
                    if not region or not realm or not guild_name:
                        continue

                    embed = discord.Embed(
                        title=_("Mythic+ Guild Scoreboard"),
                        color=await self.bot.get_embed_color(sb_msg),
                    )
                    embed.set_author(name=guild.name, icon_url=guild.icon_url)
                    tabulate_list = await self._get_dungeon_scores(
                        guild_name, max_chars, realm, region, sb_blacklist
                    )

                    embed.description = box(
                        tabulate(
                            tabulate_list,
                            headers=headers,
                            tablefmt="plain",
                            disable_numparse=True,
                        ),
                        lang="md",
                    )
                    # Don't edit if there wouldn't be a change
                    if sb_msg.embeds[0].description == embed.description:
                        continue
                    await sb_msg.edit(embed=embed)

    @staticmethod
    async def _get_dungeon_scores(
        guild_name: str,
        max_chars: int,
        realm: str,
        region: str,
        sb_blacklist: list[str],
    ):
        async with RaiderIO() as rio:
            roster = await rio.get_guild_roster(region, realm, guild_name)

            lb = {}
            # TODO: Surely there's a better way to do literally everything below
            for char in roster["guildRoster"]["roster"]:
                char_name = char["character"]["name"]
                score = char["keystoneScores"]["allScore"]

                if score > 250 and char_name.lower() not in sb_blacklist:
                    lb[char_name] = score

            lb = dict(sorted(lb.items(), key=lambda i: i[1], reverse=True))

            chars = list(lb.keys())[:max_chars]
            scores = list(lb.values())[:max_chars]

            tabulate_list = []
            for index, char_info in enumerate(zip(chars, scores)):
                char_name = char_info[0]
                char_score = char_info[1]
                tabulate_list.append(
                    [
                        f"{index + 1}.",
                        char_name,
                        humanize_number(int(char_score)),
                    ]
                )
        return tabulate_list

    async def _generate_dungeon_scoreboard(
        self, ctx: commands.Context
    ) -> discord.Embed:
        max_chars = 20
        headers = ["#", _("Name"), _("Score")]
        guild_name, realm, region, sb_blacklist = await self._get_guild_config(ctx)
        try:
            if not region:
                raise ValueError(
                    _(
                        "\nThe bot owner needs to set a region with `[p]wowset region` first."
                    )
                )
            if not realm:
                raise ValueError(
                    _(
                        "\nA server admin needs to set a realm with `[p]wowset realm` first."
                    )
                )
            if not guild_name:
                raise ValueError(
                    _(
                        "\nA server admin needs to set a guild name with `[p]wowset guild` first."
                    )
                )

            embed = discord.Embed(
                title=_("Mythic+ Guild Scoreboard"),
                color=await ctx.embed_color(),
            )
            embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
            tabulate_list = await self._get_dungeon_scores(
                guild_name, max_chars, realm, region, sb_blacklist
            )

            embed.description = box(
                tabulate(
                    tabulate_list,
                    headers=headers,
                    tablefmt="plain",
                    disable_numparse=True,
                ),
                lang="md",
            )
            return embed
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @staticmethod
    async def _delete_scoreboard(
        ctx: commands.Context, sb_channel_id: int, sb_msg_id: int
    ):
        try:
            sb_channel: discord.TextChannel = ctx.guild.get_channel(sb_channel_id)
            sb_msg: discord.Message = await sb_channel.fetch_message(sb_msg_id)
        except discord.NotFound:
            sb_msg = None
            log.info(f"Scoreboard message in {ctx.guild} ({ctx.guild.id}) not found.")
        if sb_msg:
            await sb_msg.delete()

    async def _generate_pvp_scoreboard(self, ctx: commands.Context) -> discord.Embed:
        max_chars = 10
        headers = ["#", _("Name"), _("Rating")]
        guild_name, realm, region, sb_blacklist = await self._get_guild_config(ctx)
        if not region:
            await ctx.send(
                _(
                    "\nThe bot owner needs to set a region with `[p]wowset region` first."
                )
            )
        if not realm:
            await ctx.send(
                _("\nA server admin needs to set a realm with `[p]wowset realm` first.")
            )
        if not guild_name:
            await ctx.send(
                _(
                    "\nA server admin needs to set a guild name with `[p]wowset guild` first."
                )
            )

        msg = await ctx.send(_("This may take a while..."))

        embed_pvp = discord.Embed(
            title=_("Guild PvP Leaderboard"),
            color=await ctx.embed_color(),
        )

        tabulate_lists = await self._get_pvp_scores(
            ctx, guild_name, max_chars, realm, region, sb_blacklist
        )

        embed_pvp.add_field(
            name=_("RBG Leaderboard"),
            value=box(
                tabulate(
                    tabulate_lists[0],
                    headers=headers,
                    tablefmt="plain",
                    disable_numparse=True,
                ),
                lang="md",
            ),
            inline=False,
        )
        embed_pvp.add_field(
            name=_("2v2 Arena Leaderboard"),
            value=box(
                tabulate(
                    tabulate_lists[1],
                    headers=headers,
                    tablefmt="plain",
                    disable_numparse=True,
                ),
                lang="md",
            ),
            inline=False,
        )
        embed_pvp.add_field(
            name=_("3v3 Arena Leaderboard"),
            value=box(
                tabulate(
                    tabulate_lists[2],
                    headers=headers,
                    tablefmt="plain",
                    disable_numparse=True,
                ),
                lang="md",
            ),
            inline=False,
        )

        await msg.delete()
        return embed_pvp

    async def _get_pvp_scores(
        self,
        ctx,
        guild_name: str,
        max_chars: int,
        realm: str,
        region: str,
        sb_blacklist: list[str],
    ) -> list:
        limiter = AsyncLimiter(33, time_period=1)
        api_client: BlizzardApi = await get_api_client(self.bot, ctx)
        guild_name = guild_name.replace(" ", "-").lower()

        fetch_current_season = functools.partial(
            api_client.wow.game_data.get_pvp_seasons_index,
            region=region,
            locale="en_US",
        )
        current_season: int = (
            await self.bot.loop.run_in_executor(None, fetch_current_season)
        )["current_season"]["id"]

        fetch_guild_roster = functools.partial(
            api_client.wow.profile.get_guild_roster,
            region=region,
            realm_slug=realm,
            locale="en_US",
            name_slug=guild_name,
        )
        guild_roster = await self.bot.loop.run_in_executor(None, fetch_guild_roster)

        roster = {"rbg": {}, "2v2": {}, "3v3": {}}

        for member in guild_roster["members"]:
            async with limiter:
                character_name = member["character"]["name"].lower()
                if character_name not in sb_blacklist:
                    fetch_rbg_statistics = functools.partial(
                        api_client.wow.profile.get_character_pvp_bracket_statistics,
                        region=region,
                        realm_slug=realm,
                        character_name=character_name,
                        locale="en_US",
                        pvp_bracket="rbg",
                    )
                    fetch_duo_statistics = functools.partial(
                        api_client.wow.profile.get_character_pvp_bracket_statistics,
                        region=region,
                        realm_slug=realm,
                        character_name=character_name,
                        locale="en_US",
                        pvp_bracket="2v2",
                    )
                    fetch_tri_statistics = functools.partial(
                        api_client.wow.profile.get_character_pvp_bracket_statistics,
                        region=region,
                        realm_slug=realm,
                        character_name=character_name,
                        locale="en_US",
                        pvp_bracket="3v3",
                    )

                    rbg_statistics = await self.bot.loop.run_in_executor(
                        None, fetch_rbg_statistics
                    )
                    duo_statistics = await self.bot.loop.run_in_executor(
                        None, fetch_duo_statistics
                    )
                    tri_statistics = await self.bot.loop.run_in_executor(
                        None, fetch_tri_statistics
                    )

                    if "rating" in rbg_statistics:
                        # Have to nest this because there won't be a season key if
                        # the character never played the gamemode
                        if rbg_statistics["season"]["id"] == current_season:
                            roster["rbg"][character_name] = rbg_statistics["rating"]
                            logging.debug(
                                f"{character_name} has RBG rating {rbg_statistics['rating']}"
                            )
                    if "rating" in duo_statistics:
                        if duo_statistics["season"]["id"] == current_season:
                            roster["2v2"][character_name] = duo_statistics["rating"]
                            logging.debug(
                                f"{character_name} has 2v2 rating {duo_statistics['rating']}"
                            )
                    if "rating" in tri_statistics:
                        if tri_statistics["season"]["id"] == current_season:
                            roster["3v3"][character_name] = tri_statistics["rating"]
                            logging.debug(
                                f"{character_name} has 3v3 rating {tri_statistics['rating']}"
                            )

        roster["rbg"] = dict(
            sorted(roster["rbg"].items(), key=lambda i: i[1], reverse=True)
        )
        roster["2v2"] = dict(
            sorted(roster["2v2"].items(), key=lambda i: i[1], reverse=True)
        )
        roster["3v3"] = dict(
            sorted(roster["3v3"].items(), key=lambda i: i[1], reverse=True)
        )

        characters_rbg = list(roster["rbg"].keys())[:max_chars]
        characters_2v2 = list(roster["2v2"].keys())[:max_chars]
        characters_3v3 = list(roster["3v3"].keys())[:max_chars]
        ratings_rbg = list(roster["rbg"].values())[:max_chars]
        ratings_2v2 = list(roster["2v2"].values())[:max_chars]
        ratings_3v3 = list(roster["3v3"].values())[:max_chars]

        tabulate_lists = [[], [], []]  # [RBG, 2v2, 3v3]
        for index, char_info in enumerate(zip(characters_rbg, ratings_rbg)):
            char_name: str = char_info[0]
            char_rating: int = char_info[1]
            tabulate_lists[0].append(
                [
                    f"{index + 1}.",
                    char_name.capitalize(),
                    humanize_number(int(char_rating)),
                ]
            )
        for index, char_info in enumerate(zip(characters_2v2, ratings_2v2)):
            char_name: str = char_info[0]
            char_rating: int = char_info[1]
            tabulate_lists[1].append(
                [
                    f"{index + 1}.",
                    char_name.capitalize(),
                    humanize_number(int(char_rating)),
                ]
            )
        for index, char_info in enumerate(zip(characters_3v3, ratings_3v3)):
            char_name: str = char_info[0]
            char_rating: int = char_info[1]
            tabulate_lists[2].append(
                [
                    f"{index + 1}.",
                    char_name.capitalize(),
                    humanize_number(int(char_rating)),
                ]
            )
        return tabulate_lists

    async def _get_guild_config(self, ctx):
        region: str = await self.config.guild(ctx.guild).region()
        realm: str = await self.config.guild(ctx.guild).realm()
        guild_name: str = await self.config.guild(ctx.guild).real_guild_name()
        sb_blacklist: list[str] = await self.config.guild(
            ctx.guild
        ).scoreboard_blacklist()
        return guild_name, realm, region, sb_blacklist
