import os.path
import shutil
import aiohttp
from io import BytesIO
from PIL import Image

from redbot.core import commands
from redbot.core import data_manager
import discord


HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64)"}


class Jahaci(commands.Cog):
    """
    Kolekcija naredbi napravljene za WoW guild Jahaci Rumene Kadulje
    """

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(headers=HEADER)
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
                data_dir = str(data_manager.cog_data_path(self))
                output_dir = data_dir + "/emote-output/"
                archive = data_dir + "/emote-output.zip"
                emoji_format = ".tga"

                if os.path.isdir(output_dir):
                    shutil.rmtree(output_dir)
                os.mkdir(output_dir)

                for emoji in ctx.guild.emojis:
                    emoji_name = str(emoji.name)
                    emoji_url = str(emoji.url)
                    async with self.session.get(emoji_url) as resp:
                        if resp.status == 200:
                            emoji_img = Image.open(BytesIO(await resp.read()))
                            emoji_img.save(output_dir + emoji_name + emoji_format)
                shutil.make_archive(
                    data_dir + "/emote-output", "zip", data_dir, "emote-output"
                )

                file = discord.File(archive)
                await ctx.send(file=file)

                shutil.rmtree(output_dir)
                os.remove(archive)
            except Exception as e:
                await ctx.send(e)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
