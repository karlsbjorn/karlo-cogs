from typing import List

import discord
import gspread_asyncio
from google.oauth2.service_account import Credentials
from redbot.core import commands, data_manager
from redbot.core.i18n import Translator
from redbot.core.utils import menus, chat_formatting
from redbot.core.utils.menus import DEFAULT_CONTROLS

_ = Translator("WoWTools", __file__)

MEMBERS_PER_PAGE = 20


class Wowaudit:
    @commands.group()
    async def wow(self, ctx):
        """Commands for interacting with World of Warcraft"""
        pass

    @wow.command()
    async def ilvl(self, ctx):
        """Display current equipped item level of your wowaudit group."""
        try:
            async with ctx.typing():
                embeds = await self.gen_avg_ilvl(ctx)
                await menus.menu(ctx, embeds, DEFAULT_CONTROLS)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    async def gen_avg_ilvl(self, ctx) -> List[discord.Embed]:
        ss, ws = await self.get_summary_sheet()

        sheet_title = await ss.get_title()
        member_count = int((await ws.acell("H5")).value)
        members = await ws.get_values("C9:F" + str(9 + (member_count - 1)))

        avg_ilvl_output = ""
        embeds = []
        embed_colour = await ctx.embed_color()
        page_n = 0
        for member in members:
            member_rank = member[0]
            member_name = member[1]
            member_ilvl = member[3]

            avg_ilvl_output += _(
                "{member_rank}. {member_name} - {member_ilvl}\n"
            ).format(
                member_rank=member_rank,
                member_name=member_name,
                member_ilvl=chat_formatting.bold(member_ilvl),
            )
            if (int(member_rank) % MEMBERS_PER_PAGE) == 0:
                page_n += 1
                embed = await self.gen_avg_ilvl_page(
                    ctx, page_n, sheet_title, avg_ilvl_output
                )
                embeds.append(embed)
                avg_ilvl_output = ""
        if avg_ilvl_output != "":
            page_n += 1
            embed = await self.gen_avg_ilvl_page(
                ctx, page_n, sheet_title, avg_ilvl_output
            )
            embeds.append(embed)
        return embeds

    @staticmethod
    async def gen_avg_ilvl_page(
        ctx,
        page_n: int,
        sheet_title: str,
        avg_ilvl_output: str,
    ) -> discord.Embed:
        colour = await ctx.embed_color()
        embed = discord.Embed(
            colour=colour,
        )
        embed.set_author(name=sheet_title, icon_url=ctx.guild.icon_url)
        embed.add_field(name=_("Average Item Level"), value=avg_ilvl_output)
        embed.set_footer(text=_("Page {page_number}").format(page_number=page_n))
        return embed

    @wow.command()
    async def tier(self, ctx):
        """Display current equipped tier pieces of your wowaudit group."""
        try:
            async with ctx.typing():
                embeds = await self.gen_tier(ctx)
                await menus.menu(ctx, embeds, DEFAULT_CONTROLS)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    async def gen_tier(self, ctx) -> List[discord.Embed]:
        ss, ws = await self.get_summary_sheet()

        sheet_title = await ss.get_title()
        member_count = int((await ws.acell("H5")).value)
        members = await ws.get_values("H9:O" + str(9 + (member_count - 1)))

        member_tier_output = ""
        embeds = []
        page_n = 0
        for member in members:
            member_rank = member[0]
            member_name = member[1]
            member_tier_n = member[2]
            member_tier = (
                member[3],  # Head
                member[4],  # Shoulder
                member[5],  # Chest
                member[6],  # Gloves
                member[7],  # Legs
            )

            member_tier_output += _(
                "{member_rank}. {member_name} - {member_tier_n} - **({member_tier})**\n"
            ).format(
                member_rank=member_rank,
                member_name=member_name,
                member_tier_n=member_tier_n,
                member_tier=" ".join(member_tier),
            )
            if (int(member_rank) % MEMBERS_PER_PAGE) == 0:
                page_n += 1
                embed = await self.gen_tier_page(
                    ctx, page_n, sheet_title, member_tier_output
                )
                embeds.append(embed)
                member_tier_output = ""
        if member_tier_output != "":
            page_n += 1
            embed = await self.gen_tier_page(
                ctx, page_n, sheet_title, member_tier_output
            )
            embeds.append(embed)
        return embeds

    @staticmethod
    async def gen_tier_page(
        ctx,
        page_n: int,
        sheet_title: str,
        member_tier_output: str,
    ) -> discord.Embed:
        colour = await ctx.embed_color()
        embed = discord.Embed(
            colour=colour,
        )
        embed.set_author(name=sheet_title, icon_url=ctx.guild.icon_url)
        embed.add_field(name=_("Tier Pieces Obtained"), value=member_tier_output)
        embed.set_footer(text=_("Page {page_number}").format(page_number=page_n))
        return embed

    async def get_summary_sheet(self):
        agcm = gspread_asyncio.AsyncioGspreadClientManager(self.get_creds)
        agc = await agcm.authorize()

        wowaudit_key = await self.config.wowaudit_key()

        ss = await agc.open_by_key(wowaudit_key)
        ws = await ss.get_worksheet(0)
        return ss, ws

    def get_creds(self):
        creds_path = str(data_manager.cog_data_path(self)) + "/service_account.json"
        creds = Credentials.from_service_account_file(creds_path)
        scoped = creds.with_scopes(
            [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
        )
        return scoped
