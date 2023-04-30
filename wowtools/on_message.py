import itertools
import re
from io import BytesIO
from typing import List

import discord
from aiohttp import ClientResponseError
from PIL import Image
from redbot.core import commands

from .utils import get_api_client


class OnMessage:
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if not await self.is_valid(message):
            return
        if not await self.config.guild(message.guild).on_message():
            return

        search_strings = self.extract_search_string(message.content)
        if not search_strings:
            return

        embeds = await self.get_embeds(search_strings)
        if not embeds:
            return

        await message.channel.send(embeds=embeds)

    async def is_valid(self, message: discord.Message) -> bool:
        # sourcery skip
        # check whether the message was sent in a guild
        if message.guild is None:
            return False
        # check whether the message author isn't a bot
        if message.author.bot:
            return False
        # check whether the bot can send and delete messages in the given channel
        channel_perms = message.channel.permissions_for(message.guild)
        if not channel_perms.send_messages:
            return False
        # check whether the cog isn't disabled
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return False
        # check whether the channel isn't on the ignore list
        if not await self.bot.ignored_channel_or_guild(message):
            return False
        # check whether the message author isn't on allowlist/blocklist
        if not await self.bot.allowed_by_whitelist_blacklist(message.author):
            return False
        return True

    @staticmethod
    def extract_search_string(string: str) -> List[str]:
        pattern = r"\[\[(.*?)\]\]"
        return re.findall(pattern, string)

    async def get_embeds(self, search_strings: List[str]) -> List[discord.Embed]:
        try:
            api_client = await get_api_client(self.bot, "us")
        except Exception:
            return []

        embeds = []
        for search_string in search_strings[:5]:
            await self.search_for_string(api_client, embeds, search_string)

        return embeds

    async def search_for_string(self, api_client, embeds, search_string):
        async with api_client:
            search_params = {
                "name.en_US": search_string,
                "orderby": "id",
                "_page": 1,
            }
            search_methods = [  # Currently only 1 method, but this is for future expansion
                [
                    api_client.Retail.GameData.get_spell_search,
                    api_client.Retail.GameData.get_spell_media,
                    api_client.Retail.GameData.get_spell,
                ]
            ]
            await self.start_searching(embeds, search_methods, search_params, search_string)

    async def start_searching(self, embeds, search_methods, search_params, search_string):
        for method in search_methods:
            search_method = method[0]
            media_method = method[1]
            description_method = method[2]

            try:
                await self.limiter.acquire()
                search_results = await search_method(search_params)
            except ClientResponseError:
                continue

            for result in search_results["results"]:
                if result["data"]["name"]["en_US"].lower() != search_string.lower():
                    continue
                embeds.append(await self.make_embed(description_method, media_method, result))
                break

    async def make_embed(self, description_method, media_method, result):
        result_description = await description_method(result["data"]["id"])
        result_icon = await media_method(result["data"]["id"])
        embed = discord.Embed(
            title=result["data"]["name"]["en_US"],
            description=result_description["description"],
            url=f"https://www.wowhead.com/spell={result['data']['id']}",
            colour=await self.get_embed_colour(result_icon["assets"][0]["value"]),
        )
        embed.set_thumbnail(url=result_icon["assets"][0]["value"])
        return embed

    async def get_embed_colour(self, url: str) -> discord.Color:
        """Get the average colour of an image by averaging the RGB values of all pixels."""
        async with self.session.get(url) as response:
            img = BytesIO(await response.read())
        img.seek(0)

        image = Image.open(img)
        width, height = image.size

        total_r = total_g = total_b = 0
        for x, y in itertools.product(range(width), range(height)):
            r, g, b = image.getpixel((x, y))
            total_r += r
            total_g += g
            total_b += b

        pixels = width * height
        avg_r = total_r // pixels
        avg_g = total_g // pixels
        avg_b = total_b // pixels
        return discord.Color.from_rgb(avg_r, avg_g, avg_b)
