import discord

from redbot.core import commands, data_manager, utils
from redbot.core.i18n import Translator
from redbot.core.utils import menus, chat_formatting
from redbot.core.utils.menus import DEFAULT_CONTROLS

import gspread_asyncio
from google.oauth2.service_account import Credentials
from datetime import datetime

_ = Translator("WoWTools", __file__)


class Wowaudit:

    @commands.group()
    async def wow(self, ctx):
        pass

    @wow.command()
    async def ilvl(self, ctx):
        async with ctx.typing():
            agcm = gspread_asyncio.AsyncioGspreadClientManager(self.get_creds)
            agc = await agcm.authorize()

            wowaudit_key = await self.config.wowaudit_key()

            ss = await agc.open_by_key(wowaudit_key)
            ws = await ss.get_worksheet(0)

            sheet_title = await ss.get_title()
            member_count = int((await ws.acell('H5')).value)
            members = await ws.get_values('C9:F' + str(9 + (member_count - 1)))

            avg_ilvl_output = ''
            embeds = []
            page = 0
            members_per_page = 20
            # TODO: tabulate
            for member in members:
                member_rank = member[0]
                member_name = member[1]
                member_ilvl = member[3]

                avg_ilvl_output += "{member_rank}. {member_name} - {member_ilvl}\n".format(member_rank=member_rank,member_name=member_name,member_ilvl=chat_formatting.bold(member_ilvl))
                if (int(member_rank) % members_per_page) == 0:
                    page += 1
                    embed = discord.Embed(title=sheet_title, timestamp=datetime.utcnow())
                    embed.add_field(name="Average Item Level", value=avg_ilvl_output)
                    embed.set_footer(text="Stranica " + str(page) + " - U slučaju krivih informacija obratite se @jasko")
                    embeds.append(embed)
                    avg_ilvl_output = ''
            if avg_ilvl_output != '':
                page += 1
                embed = discord.Embed(title=sheet_title, timestamp=datetime.utcnow())
                embed.add_field(name="Average Item Level", value=avg_ilvl_output)
                embed.set_footer(text="Stranica " + str(page) + " - U slučaju krivih informacija obratite se @jasko")
                embeds.append(embed)

            await menus.menu(ctx, embeds, DEFAULT_CONTROLS)

    def get_creds(self):
        creds_path = str(data_manager.cog_data_path(self)) + "/service_account.json"
        creds = Credentials.from_service_account_file(creds_path)
        scoped = creds.with_scopes([
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ])
        return scoped
