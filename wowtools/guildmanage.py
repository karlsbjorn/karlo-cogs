import logging
from typing import Dict

import dictdiffer
import discord
from discord.ext import tasks
from redbot.core import commands
from redbot.core.i18n import Translator

from .utils import get_api_client

_ = Translator("WoWTools", __file__)
log = logging.getLogger("red.karlo-cogs.wowtools")


class GuildManage:
    @commands.group()
    @commands.admin()
    async def gmset(self, ctx: commands.Context):
        """Configure guild management."""
        pass

    @gmset.command()
    @commands.admin()
    async def rankstring(self, ctx: commands.Context, rank: int, *, rank_string: str):
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

    @commands.command()
    @commands.guild_only()
    async def guildlog(self, ctx: commands.Context, channel: discord.TextChannel | discord.Thread):
        """Set the channel for guild logs."""
        await self.config.guild(ctx.guild).guild_log_channel.set(channel.id)
        guild_roster = await self.get_guild_roster(ctx.guild)
        await self.config.guild(ctx.guild).guild_roster.set(guild_roster)
        await ctx.send(_("Guild log channel set to {channel}.").format(channel=channel.mention))

    @tasks.loop(hours=1)
    async def guild_log(self):
        for guild in self.bot.guilds:
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
                for member in diff[2]:
                    member_name = member[0]
                    member_rank = await self.get_rank_string(guild, member[1])
                    embed = discord.Embed(
                        title=_("**{member}** joined the guild as **{rank}**.").format(
                            member=member_name, rank=member_rank
                        ),
                        color=discord.Colour.green(),
                    )
                    embeds.append(embed)
            elif diff[0] == "change":
                member_name = diff[1]
                member_rank = await self.get_rank_string(guild, diff[2][1])
                embed = discord.Embed(
                    title=_("**{member}** was promoted to **{rank}**.").format(
                        member=member_name, rank=member_rank
                    ),
                    color=discord.Colour.blurple(),
                )
                embeds.append(embed)
            elif diff[0] == "remove":
                for member in diff[2]:
                    member_name = member[0]
                    member_rank = await self.get_rank_string(guild, member[1])
                    embed = discord.Embed(
                        title=_("**{member} ({rank})** left the guild.").format(
                            member=member_name, rank=member_rank
                        ),
                        color=discord.Colour.red(),
                    )
                    embeds.append(embed)
        return embeds

    @guild_log.error
    async def guild_log_error(self, error):
        log.error(f"Unhandled exception in guild_log task: {error}", exc_info=True)

    async def get_rank_string(self, guild: discord.Guild, rank: int) -> str:
        rank_strings: dict = await self.config.guild(guild).guild_rankstrings()
        return rank_strings.get(str(rank), f"Rank {rank}")
