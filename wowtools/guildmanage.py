import logging
from typing import Dict

import dictdiffer
import discord
from discord.ext import tasks
from rapidfuzz import fuzz, process, utils
from redbot.core import commands
from redbot.core.i18n import Translator, set_contextual_locales_from_guild
from redbot.core.utils.chat_formatting import humanize_list
from tabulate import tabulate

from .utils import get_api_client

_ = Translator("WoWTools", __file__)
log = logging.getLogger("red.karlo-cogs.wowtools")


class GuildManage:
    @commands.group()
    @commands.admin()
    @commands.guild_only()
    async def gmset(self, ctx: commands.Context):
        """Configure guild management."""
        pass

    @gmset.command(name="rankstring")
    @commands.admin()
    async def gmset_rankstring(self, ctx: commands.Context, rank: int, *, rank_string: str):
        """Bind a rank to a string."""
        if rank not in range(1, 11):
            await ctx.send(_("Rank must be between 1 and 10."))
            return
        await self.config.guild(ctx.guild).guild_rankstrings.set_raw(rank, value=rank_string)
        await ctx.send(
            _("**{rank_string}** bound to **Rank {rank}**.").format(
                rank_string=rank_string, rank=rank
            )
        )

    @gmset.command(name="rankrole")
    @commands.admin()
    async def gmset_rankrole(self, ctx: commands.Context, rank: int, role: discord.Role):
        """Bind a rank to a role."""
        if rank not in range(1, 11):
            await ctx.send(_("Rank must be between 1 and 10."))
            return
        await self.config.guild(ctx.guild).guild_rankroles.set_raw(rank, value=role.id)
        await ctx.send(_("**{role}** bound to **Rank {rank}**.").format(role=role.name, rank=rank))

    @gmset.command(name="view")
    @commands.admin()
    async def gmset_view(self, ctx: commands.Context):
        """View guild rank settings."""
        guild: discord.Guild = ctx.guild
        rank_strings = await self.config.guild(guild).guild_rankstrings.get_raw()
        rank_roles = await self.config.guild(guild).guild_rankroles.get_raw()

        table_data = []
        for rank in range(1, 11):
            rank_string = rank_strings.get(str(rank), "")
            role_id = rank_roles.get(str(rank), None)
            role = guild.get_role(role_id) if role_id else None

            table_data.append([rank, rank_string, f"@{role.name}" if role else ""])

        headers = [_("Rank"), _("Rank String"), _("Rank Role")]
        table = tabulate(table_data, headers, tablefmt="plain")

        embed = discord.Embed(
            title=_("Rank Settings"), description=f"```{table}```", color=await ctx.embed_color()
        )
        await ctx.send(embed=embed)

    @gmset.command()
    @commands.admin()
    async def guild_name(self, ctx: commands.Context, *, guild_name: str):
        """Set the guild name to be used in the guild management commands."""
        try:
            async with ctx.typing():
                if guild_name is None:
                    await self.config.guild(ctx.guild).gmanage_guild.clear()
                    await ctx.send(_("Guild name cleared."))
                    return
                guild_name = guild_name.replace(" ", "-").lower()
                await self.config.guild(ctx.guild).gmanage_guild.set(guild_name)
            await ctx.send(_("Guild name set."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @gmset.command()
    @commands.admin()
    async def guild_realm(self, ctx: commands.Context, guild_realm: str):
        """Set the realm of the guild."""
        try:
            async with ctx.typing():
                if guild_realm is None:
                    await self.config.guild(ctx.guild).gmanage_realm.clear()
                    await ctx.send(_("Guild realm cleared."))
                    return
                guild_realm = guild_realm.replace(" ", "-").lower()
                await self.config.guild(ctx.guild).gmanage_realm.set(guild_realm)
            await ctx.send(_("Guild realm set."))
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    async def get_guild_roster(self, guild: discord.Guild) -> Dict[str, int]:
        """
        Get guild roster from Blizzard's API.

        :param guild:
        :return: dict containing guild members and their rank
        """
        wow_guild_name: str = await self.config.guild(guild).gmanage_guild()
        wow_guild_name = wow_guild_name.lower()
        region: str = await self.config.guild(guild).region()
        realm: str = await self.config.guild(guild).gmanage_realm()
        realm = realm.lower()

        api_client = await get_api_client(self.bot, region)
        async with api_client as wow_client:
            wow_client = wow_client.Retail
            guild_roster = await wow_client.Profile.get_guild_roster(
                name_slug=wow_guild_name, realm_slug=realm
            )

        roster: Dict[str, int] = {
            member["character"]["name"]: member["rank"] + 1 for member in guild_roster["members"]
        }
        return roster

    @gmset.command()
    @commands.guild_only()
    async def guildlog(self, ctx: commands.Context, channel: discord.TextChannel | discord.Thread):
        """Set the channel for guild logs."""
        await self.config.guild(ctx.guild).guild_log_channel.set(channel.id)
        guild_roster = await self.get_guild_roster(ctx.guild)
        await self.config.guild(ctx.guild).guild_roster.set(guild_roster)
        await ctx.send(_("Guild log channel set to {channel}.").format(channel=channel.mention))

    @tasks.loop(minutes=5)
    async def guild_log(self):
        for guild in self.bot.guilds:
            if await self.bot.cog_disabled_in_guild(self, guild):
                continue
            await set_contextual_locales_from_guild(self.bot, guild)

            guild_log_channel: int = await self.config.guild(guild).guild_log_channel()
            if guild_log_channel is None:
                continue
            guild_log_channel: discord.TextChannel | discord.Thread = guild.get_channel_or_thread(
                guild_log_channel
            )
            if guild_log_channel is None:
                continue

            log.debug("Comparing guild rosters.")
            current_roster = await self.get_guild_roster(guild)
            previous_roster = await self.config.guild(guild).guild_roster()
            difference = list(dictdiffer.diff(previous_roster, current_roster))
            if not difference:
                log.debug("No difference in guild roster.")
                continue

            embeds = await self.get_event_embeds(difference, guild)
            await self.config.guild(guild).guild_roster.set(current_roster)

            for i in range((len(embeds) // 10) + 1):
                await guild_log_channel.send(embeds=embeds[i * 10 : (i + 1) * 10])

    async def get_event_embeds(self, difference, guild):
        embeds = []
        for diff in difference:
            if diff[0] == "add":
                await self.add_new_members(diff, embeds, guild)
            elif diff[0] == "change":
                await self.add_changed_members(diff, embeds, guild)
            elif diff[0] == "remove":
                await self.add_removed_members(diff, embeds, guild)
        return embeds

    async def add_new_members(self, diff, embeds: list, guild: discord.Guild) -> None:
        for member in diff[2]:
            member_name = member[0]
            member_rank_new = await self.get_rank_string(guild, member[1])

            embed = discord.Embed(
                title=_("**{member}** joined the guild as **{rank}**").format(
                    member=member_name, rank=member_rank_new
                ),
                description=await self.make_description(guild, member_name),
                color=discord.Colour.green(),
            )
            embeds.append(embed)

    async def add_changed_members(self, diff, embeds: list, guild: discord.Guild) -> None:
        member_name = diff[1]
        member_rank_old = await self.get_rank_string(guild, diff[2][0])
        member_rank_new = await self.get_rank_string(guild, diff[2][1])

        embed = discord.Embed(
            title=_("**{member}** was {changed} from **{old_rank}** to **{new_rank}**").format(
                member=member_name,
                old_rank=member_rank_old,
                new_rank=member_rank_new,
                changed=_("promoted") if diff[2][0] > diff[2][1] else _("demoted"),
            ),
            description=await self.make_description(guild, member_name),
            color=discord.Colour.blurple(),
        )
        embeds.append(embed)

    async def add_removed_members(self, diff, embeds: list, guild: discord.Guild) -> None:
        for member in diff[2]:
            member_name = member[0]
            member_rank_new = await self.get_rank_string(guild, member[1])

            embed = discord.Embed(
                title=_("**{member} ({rank})** left the guild").format(
                    member=member_name, rank=member_rank_new
                ),
                description=await self.make_description(guild, member_name),
                color=discord.Colour.red(),
            )
            embeds.append(embed)

    async def make_description(self, guild: discord.Guild, member_name: str) -> str:
        realm = await self.config.guild(guild).gmanage_realm()
        region = await self.config.guild(guild).region()
        description = await self.guess_member(guild, member_name) or ""
        description += f"\n{self.get_raiderio_url(realm, region, member_name)} | "
        description += f"{self.get_warcraftlogs_url(realm, region, member_name)}"
        return description

    @staticmethod
    async def guess_member(guild: discord.Guild, member_name: str) -> str | None:
        """
        Guesses the Discord member based on their name using fuzzy string matching.

        :param guild: The Discord guild to search for the member in.
        :param member_name: The name of the character to search for.
        :return: A string containing the Discord mention of the guessed member and the percentage
        match score, or None if no member was found with a high enough match score.
        """
        choices = [member.display_name for member in guild.members]
        extract = process.extract(
            member_name,
            choices,
            scorer=fuzz.WRatio,
            limit=5,
            score_cutoff=80,
            processor=utils.default_process,
        )

        mentions = []
        for member in extract:
            mentions.append(guild.members[member[2]].mention)
        return (
            _("Discord: {member} ({percent}%)").format(
                member=humanize_list(list(mentions), style="or"), percent=str(round(extract[0][1]))
            )
            if mentions
            else None
        )

    @staticmethod
    def get_raiderio_url(realm: str, region: str, name: str) -> str:
        return (
            f"[Raider.io]"
            f"(https://raider.io/characters/{region.lower()}/{realm.lower()}/{name})"
        )

    @staticmethod
    def get_warcraftlogs_url(realm: str, region: str, name: str) -> str:
        return (
            f"[WarcraftLogs]"
            f"(https://www.warcraftlogs.com/character/{region.lower()}/{realm.lower()}/{name})"
        )

    @guild_log.error
    async def guild_log_error(self, error):
        log.error(f"Unhandled exception in guild_log task: {error}", exc_info=True)

    async def get_rank_string(self, guild: discord.Guild, rank: int) -> str:
        rank_strings: dict = await self.config.guild(guild).guild_rankstrings()
        return rank_strings.get(str(rank), f"Rank {rank}")

    @commands.group()
    @commands.guild_only()
    async def gmanage(self, ctx: commands.Context):
        """Guild management commands."""
        pass

    @gmanage.command(name="find")
    @commands.guild_only()
    async def gmanage_find(self, ctx: commands.Context, member_name: str):
        """Find a member in the guild."""
        msg = ""
        discord_member = await self.guess_member(ctx.guild, member_name)
        if discord_member:
            msg += f"{discord_member}\n"

        ingame_member = await self.guess_ingame_member(ctx.guild, member_name)
        if ingame_member:
            msg += f"{ingame_member}\n"

            rio_url = self.get_raiderio_url(
                await self.config.guild(ctx.guild).gmanage_realm(),
                await self.config.guild(ctx.guild).region(),
                member_name,
            )
            wcl_url = self.get_warcraftlogs_url(
                await self.config.guild(ctx.guild).gmanage_realm(),
                await self.config.guild(ctx.guild).region(),
                member_name,
            )
            msg += f"{rio_url} | {wcl_url}"

        embed = discord.Embed(
            description=msg or _("Nothing found."),
            color=await ctx.embed_color(),
        )

        await ctx.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=False),
        )

    async def guess_ingame_member(self, guild: discord.Guild, member_name: str) -> str | None:
        roster = await self.get_guild_roster(guild)
        extract = process.extract(
            member_name,
            roster.keys(),
            scorer=fuzz.WRatio,
            limit=5,
            score_cutoff=80,
            processor=utils.default_process,
        )
        ranks = [member[1] for member in extract]
        ingame_rank = await self.get_rank_string(guild, max(ranks))
        return (
            _("In-game: {member}\nRank: {rank}").format(
                member=humanize_list([member[0] for member in extract], style="or"),
                rank=ingame_rank,
            )
            if extract
            else None
        )
