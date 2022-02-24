import os.path
import shutil
import urllib.request
from io import BytesIO
from PIL import Image

from redbot.core import commands
from redbot.core import data_manager
import discord


# TODO: Ocisti ***sve***


class Jahaci(commands.Cog):
    """
    Kolekcija naredbi napravljene za WoW guild Jahaci Rumene Kadulje
    """

    def __init__(self, bot):
        self.bot = bot
        # TODO: Koristi Red-ov Config

    @commands.group()
    async def jrk(self, ctx):
        """JRK naredbe"""
        pass

    @jrk.command()
    @commands.is_owner()
    async def export(self, ctx):
        """Stavi u .zip sve emotikone u serveru"""
        async with ctx.typing():
            try:
                header = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64)"}
                output_dir = str(data_manager.cog_data_path(self)) + '/jrk-output/'
                emoji_format = ".tga"

                if os.path.isdir(output_dir):
                    shutil.rmtree(output_dir)
                os.mkdir(output_dir)

                for emoji in ctx.guild.emojis:
                    emoji_name = str(emoji.name)
                    emoji_url = str(emoji.url)
                    req = urllib.request.Request(emoji_url, headers=header)
                    with urllib.request.urlopen(req) as img:
                        emoji_img = Image.open(BytesIO(img.read()))
                        emoji_img.save(output_dir + emoji_name + emoji_format)
                shutil.make_archive("emote-output", "zip", output_dir)

                file = discord.File("emote-output.zip")
                await ctx.send(file=file)

                shutil.rmtree(output_dir)
                os.remove("emote-output.zip")
            except Exception as e:
                await ctx.send(e)

    #
    # Loše. Nekoristivo.
    #
    # @commands.group()
    # async def roster(self, ctx):
    #     """
    #     Generiraj discord-friendly raid roster iz Google Sheetsa
    #     """
    #     pass
    #
    # @roster.command()
    # async def heroic(self, ctx):
    #     """
    #     Heroic grupa
    #     """
    #     gc = gspread.service_account()
    #     wks = gc.open_by_key("19HCCzfBL7pbku0a2LkojgpDy1dsupEDgSCzqSS9zKZI").sheet1
    #
    #     stitle = wks.title
    #     current_raid = "Sanctum of Domination"
    #
    #     roles = wks.col_values(1)
    #     group1 = wks.col_values(2)
    #     group2 = wks.col_values(3)
    #
    #     group1_raiders = self.format_raiders(group1, roles)
    #     group2_raiders = self.format_raiders(group2, roles)
    #
    #     embed = self.create_embed(stitle, current_raid, group1_raiders, group2_raiders)
    #     await ctx.send(embed=embed)
    #
    # @roster.command()
    # async def mythic(self, ctx):
    #     """
    #     Mythic grupa
    #     """
    #     gc = gspread.service_account()
    #     sh = gc.open_by_key("19HCCzfBL7pbku0a2LkojgpDy1dsupEDgSCzqSS9zKZI")
    #     wks = sh.get_worksheet(1)
    #
    #     stitle = wks.title
    #     current_raid = "Sanctum of Domination"
    #
    #     roles = wks.col_values(1)
    #     group1 = wks.col_values(2)
    #
    #     group1_raiders = self.format_raiders(group1, roles)
    #     group2_raiders = self.format_backup_raiders(group1, roles)
    #
    #     embed = self.create_embed_mythic(stitle, current_raid, group1_raiders, group2_raiders)
    #     await ctx.send(embed=embed)
    #
    # @staticmethod
    # def format_raiders(raid_group, roles):
    #     # role_emojis = {'tank': '<:tank:865247930528956437>',
    #     #                'healer': '<:healer:865247920830939157>',
    #     #                'dps': '<:dps:865247908885168148>'}
    #     raiders = ""
    #     role_count = 1
    #     for raider in raid_group[1:]:
    #         if raider is not "":
    #             if roles[role_count] == "dps":
    #                 raiders = raiders + ":crossed_swords: " + raider + "\n"
    #             elif roles[role_count] == "healer":
    #                 raiders = raiders + ":green_heart: " + raider + "\n"
    #             elif roles[role_count] == "dps/heal":
    #                 raiders = raiders + ":crossed_swords:/:green_heart: " + raider + "\n"
    #             elif roles[role_count] == "dps/tank":
    #                 raiders = raiders + ":crossed_swords:/:shield: " + raider + "\n"
    #             elif roles[role_count] == "tank":
    #                 raiders = raiders + ":shield: " + raider + "\n"
    #             role_count += 1
    #     return raiders
    #
    # @staticmethod
    # def format_backup_raiders(raid_group, roles):
    #     raiders = ""
    #     role_count = 1
    #     for raider in raid_group[1:]:
    #         if raider != "":
    #             if roles[role_count] == "backup DPS:":
    #                 raiders = raiders + "<:bench:808313089551368202> :crossed_swords: " + raider + "\n"
    #             role_count += 1
    #     return raiders
    #
    # @staticmethod
    # def create_embed(title, description, group1_raiders, group2_raiders):
    #     embed = discord.Embed(
    #         title=title,
    #         url="https://docs.google.com/spreadsheets/d/19HCCzfBL7pbku0a2LkojgpDy1dsupEDgSCzqSS9zKZI/edit#gid=0",
    #         description=description,
    #         color=discord.Color.dark_blue(),
    #     )
    #
    #     embed.set_author(
    #         name="Jahaci Rumene Kadulje",
    #         icon_url="https://cdn.discordapp.com/icons/362298824854863882/815730b268ac798f826ae6fe10e4c473.png",
    #     )
    #     embed.add_field(name="Grupa 1", value=group1_raiders, inline=True)
    #     embed.add_field(name="Grupa 2", value=group2_raiders, inline=True)
    #     # embed.add_field(name='Mythic grupa', value='test', inline=True)
    #     return embed
    #
    # @staticmethod
    # def create_embed_mythic(title, description, group1_raiders, group2_raiders):
    #     embed = discord.Embed(
    #         title=title,
    #         url="https://docs.google.com/spreadsheets/d/19HCCzfBL7pbku0a2LkojgpDy1dsupEDgSCzqSS9zKZI/edit#gid=0",
    #         description=description,
    #         color=discord.Color.dark_blue(),
    #     )
    #
    #     embed.set_author(
    #         name="Jahaci Rumene Kadulje",
    #         icon_url="https://cdn.discordapp.com/icons/362298824854863882/815730b268ac798f826ae6fe10e4c473.png",
    #     )
    #     embed.add_field(name="Mythic roster", value=group1_raiders, inline=True)
    #     embed.add_field(name="Backup", value=group2_raiders, inline=True)
    #     return embed
