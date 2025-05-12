import itertools
import logging
import re
from io import BytesIO
from typing import List, Optional

import discord
from aiohttp import ClientResponseError
from PIL import Image
from redbot.core import commands

from wowtools.exceptions import InvalidBlizzardAPI

log = logging.getLogger("red.karlo-cogs.wowtools")


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

        try:
            embeds = await self.get_embeds(search_strings)
        except InvalidBlizzardAPI:
            log.warning(
                "The Blizzard API is not properly set up.\n"
                "Create a client on https://develop.battle.net/ and then type in "
                "`{prefix}set api blizzard client_id,whoops client_secret,whoops` "
                "filling in `whoops` with your client's ID and secret.\nThen `{prefix}reload wowtools`"
            )
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
        channel_perms = message.channel.permissions_for(message.guild.me)
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
        api_client = self.blizzard.get("us")
        if not api_client:
            raise InvalidBlizzardAPI

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
                "_pageSize": 1000,
            }
            search_methods = [  # Currently only 1 method, but this is for future expansion
                [
                    api_client.Retail.GameData.get_spell_search,
                    api_client.Retail.GameData.get_spell_media,
                    api_client.Retail.GameData.get_spell,
                    "spell",
                ],
                [
                    api_client.Retail.GameData.get_item_search,
                    api_client.Retail.GameData.get_item_media,
                    api_client.Retail.GameData.get_item,
                    "item",
                ],
            ]
            await self.start_searching(embeds, search_methods, search_params, search_string)

    async def start_searching(self, embeds, search_methods, search_params, search_string):
        for method in search_methods:
            search_method = method[0]
            media_method = method[1]
            description_method = method[2]
            obj_type = method[3]

            try:
                await self.limiter.acquire()
                search_results = await search_method(search_params)
            except ClientResponseError:
                continue

            for result in search_results["results"]:
                if result["data"]["name"]["en_US"].lower() != search_string.lower():
                    continue
                result_id = result["data"]["id"]
                embed = await self.get_or_fetch_embed(
                    media_method, description_method, result, result_id, obj_type
                )

                embeds.append(embed)
                break

    async def get_or_fetch_embed(
        self, media_method, description_method, result, result_id, obj_type
    ):
        if self.on_message_cache.get(result_id):
            embed = self.on_message_cache.get(result_id)
        else:
            embed = await self.make_embed(description_method, media_method, result, obj_type)
            self.on_message_cache[result_id] = embed
        return embed

    async def make_embed(self, description_method, media_method, result, obj_type):
        result_description = await description_method(result["data"]["id"])
        result_icon = await media_method(result["data"]["id"])
        embed = discord.Embed(
            title=result["data"]["name"]["en_US"],
            description=self.generate_description(result_description, obj_type),
            url=f"https://www.wowhead.com/{obj_type}={result['data']['id']}",
            colour=(
                await self.get_spell_colour(result_icon["assets"][0]["value"])
                if obj_type == "spell"
                else self.get_item_rarity_color(result_description.get("quality"))
            ),
        )
        embed.set_thumbnail(url=result_icon["assets"][0]["value"])
        return embed

    def generate_description(self, description, obj_type):
        if obj_type == "spell":
            return description["description"]
        if obj_type == "item" and description.get("preview_item"):
            preview = description["preview_item"]
            generated_str = ""
            if preview.get("level"):
                generated_str += f"**{preview['level']['display_string']}**"
            if preview.get("binding"):
                generated_str += f"\n{preview['binding']['name']}"

            # if preview.get("item_class"):
            #     generated_str += f"\n{preview['item_class']['name']}"
            if preview.get("item_subclass"):
                generated_str += f"\n{preview['item_subclass']['name']}"
            if preview.get("inventory_type"):
                generated_str += f" - {preview['inventory_type']['name']}\n"

            if preview.get("weapon"):
                generated_str += (
                    f"{preview['weapon']['damage']['display_string']}\n"
                    f"{preview['weapon']['dps']['display_string']}\n"
                )

            if preview.get("stats"):
                for stat in preview["stats"]:
                    generated_str += f"\n{stat['display']['display_string']}"

            if preview.get("spells"):
                generated_str += "\n".join(
                    [
                        f"\n\n**{spell['spell']['name']}**\n{spell['description']}"
                        for spell in preview["spells"]
                    ]
                )

            if preview.get("requirements") and preview["requirements"].get("level"):
                generated_str += f"\n\n{preview['requirements']['level']['display_string']}"
            return generated_str

    async def get_spell_colour(self, url: str) -> discord.Color:
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

    def get_item_rarity_color(self, rarity: Optional[dict]) -> discord.Color:
        if not rarity:
            return discord.Color.blurple()
        else:
            rarity = rarity["type"]
        if rarity.lower() == "poor":
            return discord.Color.from_str("#9d9d9d")
        if rarity.lower() == "common":
            return discord.Color.from_str("#ffffff")
        if rarity.lower() == "uncommon":
            return discord.Color.from_str("#1eff00")
        if rarity.lower() == "rare":
            return discord.Color.from_str("#0070dd")
        if rarity.lower() == "epic":
            return discord.Color.from_str("#a335ee")
        if rarity.lower() == "legendary":
            return discord.Color.from_str("#ff8000")
        if rarity.lower() == "artifact":
            return discord.Color.from_str("#e6cc80	")
        if rarity.lower() == "heirloom":
            return discord.Color.from_str("#00ccff")
        if rarity.lower() == "wow_token":
            return discord.Color.from_str("#00ccff")
        return discord.Color.blurple()
