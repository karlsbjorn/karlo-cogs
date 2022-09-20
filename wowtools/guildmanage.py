from typing import Dict, List

import discord
from rapidfuzz import fuzz, process
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import pagify

from .utils import get_api_client

_ = Translator("WoWTools", __file__)


class GuildManage:
    @commands.group(hidden=True)
    async def gm(self, ctx: commands.Context):
        """Manage guild member roles."""
        pass

    @gm.command()
    @commands.admin_or_permissions()
    async def manual(self, ctx: commands.Context):
        """Suggest proper roles for guild members."""
        async with ctx.typing():
            roster: Dict[str, int] = await self.get_guild_roster(ctx)
            if not roster:
                await ctx.send(
                    _(
                        "No guild characters with syncable ranks found.\n"
                        "Make sure you've set everything up correctly with `{prefix}gmset`. "
                    ).format(prefix=ctx.prefix)
                )
                return

            found_chars: Dict[discord.Member, str] = {}
            discord_members: List[discord.Member] = ctx.guild.members
            for discord_member in discord_members:
                discord_member_nickname = discord_member.display_name.lower().title()
                roster_members = list(roster.keys())
                match = process.extract(
                    discord_member_nickname,
                    roster_members,
                    scorer=fuzz.partial_ratio,
                    limit=1,
                )
                character_name: str = match[0][0]
                if match[0][1] == 100:
                    found_chars[discord_member] = character_name
            if not found_chars:
                await ctx.send(
                    _(
                        "No matched characters found.\n"
                        "Make sure you've set everything up correctly with `{prefix}gmset`."
                    ).format(prefix=ctx.prefix)
                )
                return

            msg = ""
            rank_roles: Dict[int, int] = await self.config.guild(
                ctx.guild
            ).guild_roles()
            for discord_member, character_name in found_chars.items():
                for rank, role in rank_roles.items():
                    role = ctx.guild.get_role(role)
                    if (
                        role not in discord_member.roles
                        and int(rank) == roster[character_name]
                    ):
                        msg += _(
                            "**{member}** should have the **{role}** role.\n"
                        ).format(
                            role=role.name,
                            member=discord_member.display_name,
                            rank=rank,
                        )
                        break
            if not msg:
                await ctx.send(_("No changes found."))
                return
            for page in pagify(msg, delims=["\n"]):
                await ctx.send(page)

    @commands.group(hidden=True)
    @commands.admin()
    async def gmset(self, ctx: commands.Context):
        """Configure guild management."""
        pass

    @gmset.command()
    @commands.admin()
    async def rank(self, ctx: commands.Context, rank: int, role: discord.Role):
        """Bind a rank to a role."""
        if rank not in range(1, 11):
            await ctx.send(_("Rank must be between 1 and 10."))
            return
        if role not in ctx.guild.roles:
            await ctx.send(_("Role must be in this server."))
            return
        await self.config.guild(ctx.guild).guild_roles.set_raw(int(rank), value=role.id)
        await ctx.send(
            _("**{role}** bound to **Rank {rank}**.").format(role=role.name, rank=rank)
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

    async def get_guild_roster(self, ctx: commands.Context) -> Dict[str, int]:
        """
        Get guild roster from Blizzard's API.

        :param ctx:
        :return: dict containing guild members and their rank
        """
        wow_guild_name: str = await self.config.guild(ctx.guild).gmanage_guild()
        wow_guild_name = wow_guild_name.lower()
        region: str = await self.config.guild(ctx.guild).region()
        realm: str = await self.config.guild(ctx.guild).gmanage_realm()
        realm = realm.lower()
        api_client = await get_api_client(self.bot, ctx, region)

        guild_roster = await api_client.Retail.Profile.get_guild_roster(
            guild=wow_guild_name, realm=realm
        )

        rank_roles: Dict[int, int] = await self.config.guild(ctx.guild).guild_roles()
        ranks: List[int] = [int(rank) for rank in list(rank_roles.keys())]
        roster: Dict[str, int] = {}
        for member in guild_roster["members"]:
            member_name = member["character"]["name"]
            member_rank = member["rank"] + 1  # rank is 0-based in the API
            # ignore every member with a rank that isn't in the config
            if member_rank in ranks:
                roster[member_name] = member_rank
        return roster

    @gmset.command(hidden=True)
    @commands.is_owner()
    async def nuke(self, ctx: commands.Context):
        """(Dev) Reset all guild settings."""
        await self.config.guild(ctx.guild).guild_roles.clear()
        await self.config.guild(ctx.guild).gmanage_guild.clear()
        await self.config.guild(ctx.guild).gmanage_realm.clear()
        await ctx.send("reset")
