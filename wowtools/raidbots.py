import regex

import discord

from redbot.core import commands
from redbot.core.i18n import Translator

_ = Translator("WoWTools", __file__)

RAIDBOTS_URL = "raidbots.com"
URL_REGEX_PATTERN = regex.compile(
    r"^(?:http[s]?:\/\/)?[\w.-]+(?:\.[\w\.-]+)+[\w\-\._~:/?#[\]@!\$&'\(\)\*\+,;=.]+$"
)


class Raidbots:
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if not await self.config.auto_raidbots():
            return
        if message.guild is None:
            return
        if message.author.bot:
            return
        channel_perms = message.channel.permissions_for(message.guild)
        if not channel_perms.send_messages:
            return
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        if not await self.bot.ignored_channel_or_guild(message):
            return
        if not await self.bot.allowed_by_whitelist_blacklist(message.author):
            return

        links = self.get_links(message.content)
        if not links:
            return

        for link in links:
            if RAIDBOTS_URL and "simbot/report" in link:
                data_url = link + "/data.json"
                sim_img_url = link + "/preview.png"
                async with self.session.request("GET", data_url) as resp:
                    if resp.status != 200:
                        return
                    data = await resp.json()
                    data_simbot = data["simbot"]["meta"]["rawFormData"]
                    data_char = data_simbot["character"]

                    char_name: str = data_char["name"]
                    char_realm: str = data_char["realm"]
                    char_region: str = data_simbot["armory"]["region"]
                    char_spec: str = data["sim"]["players"][0]["specialization"]
                    char_covenant: str = data_char["covenant"]["name"]
                    sim_fight_style: str = data_simbot["fightStyle"]
                    sim_fight_length: int = data_simbot["fightLength"]
                    sim_enemy_count: int = data_simbot["enemyCount"]
                    sim_type: str = data_simbot["reportName"]
                    char_ilvl: int = data_char["items"]["averageItemLevelEquipped"]
                    char_dps: int = round(
                        data["sim"]["players"][0]["collected_data"]["dps"]["mean"]
                    )

                    armory_url = f"https://worldofwarcraft.com/en-gb/character/{char_region.lower()}/{char_realm.lower()}/{char_name.lower()}"
                    wcl_url = f"https://www.warcraftlogs.com/character/{char_region.lower()}/{char_realm.lower()}/{char_name.lower()}"
                    raiderio_url = f"https://raider.io/characters/{char_region.lower()}/{char_realm.lower()}/{char_name.lower()}"

                    embed_title = f"{char_name} ({char_realm})"
                    embed_description = f"[WoW Armory]({armory_url}) | [Warcraft Logs]({wcl_url}) | [Raider.io]({raiderio_url})"
                    embed = discord.Embed(
                        title=embed_title,
                        color=discord.Colour.gold(),
                        url=link,
                        description=embed_description,
                    )
                    embed.add_field(name=_("Spec"), value=char_spec)
                    embed.add_field(name=_("Covenant"), value=char_covenant)
                    embed.add_field(name=_("Fight Style"), value=sim_fight_style)
                    embed.add_field(name=_("Sim Type"), value=sim_type)
                    embed.add_field(
                        name=_("Number of Bosses"), value=str(sim_enemy_count)
                    )
                    embed.add_field(
                        name=_("Fight Length"),
                        value=_("{sim_fight_length} seconds").format(
                            sim_fight_length=str(sim_fight_length)
                        ),
                    )
                    embed.add_field(name=_("DPS"), value=str(char_dps))
                    embed.add_field(
                        name=_("Link"),
                        value=_("[Full Report]({link})").format(link=link),
                    )
                    embed.set_image(url=sim_img_url)

                    await message.reply(embed=embed)

    # https://github.com/kaogurai/cogs/blob/430bfc7746d33615e0ff92423421358d73681d71/antiphishing/antiphishing.py#L103
    # https://github.com/kaogurai/cogs/blob/430bfc7746d33615e0ff92423421358d73681d71/LICENSE
    @staticmethod
    def extract_urls(message: str):
        """
        Extract URLs from a message.
        """
        # Find all regex matches
        matches = URL_REGEX_PATTERN.findall(message)
        return matches

    # https://github.com/kaogurai/cogs/blob/430bfc7746d33615e0ff92423421358d73681d71/antiphishing/antiphishing.py#L111
    # https://github.com/kaogurai/cogs/blob/430bfc7746d33615e0ff92423421358d73681d71/LICENSE
    def get_links(self, message: str):
        """
        Get links from the message content.
        """
        # Remove zero-width spaces
        message = message.replace("\u200b", "")
        message = message.replace("\u200c", "")
        message = message.replace("\u200d", "")
        message = message.replace("\u2060", "")
        message = message.replace("\uFEFF", "")
        if message != "":
            links = self.extract_urls(message)
            if not links:
                return
            return list(set(links))
