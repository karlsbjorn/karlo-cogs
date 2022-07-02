from datetime import timedelta

import discord
from dateutil.parser import isoparse
from discord.ext import tasks
from raiderio_async import RaiderIO
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box, humanize_number
from tabulate import tabulate

_ = Translator("WoWTools", __file__)


class Raiderio:
    """Cog for interaction with the raider.io API"""

    @commands.group(aliases=["rio"])
    async def raiderio(self, ctx: commands.Context):
        """Commands for interacting with Raider.io"""
        pass

    @raiderio.command(name="profile")
    async def raiderio_profile(self, ctx, character: str, *realm: str) -> None:
        """Display the raider.io profile of a character.

        Example:
        [p]raiderio profile Karlo Ragnaros
        """
        async with ctx.typing():
            region: str = await self.config.region()
            realm = "-".join(realm).lower()
            try:
                if not region:
                    raise ValueError(
                        _(
                            "\nThe bot owner needs to set a region with `[p]wowset region` first."
                        )
                    )
                if realm == "":
                    raise ValueError(_("You didn't give me a realm."))
                async with RaiderIO() as rio:
                    profile_data = await rio.get_character_profile(
                        region,
                        realm,
                        character,
                        fields=[
                            "mythic_plus_scores_by_season:current",
                            "raid_progression",
                            "gear",
                            "covenant",
                        ],
                    )

                    # TODO: Dict?
                    char_name = profile_data["name"]
                    char_race = profile_data["race"]
                    char_spec = profile_data["active_spec_name"]
                    char_class = profile_data["class"]
                    char_image = profile_data["thumbnail_url"]
                    char_score = profile_data["mythic_plus_scores_by_season"][0][
                        "segments"
                    ]["all"]
                    char_score_color = int("0x" + char_score["color"][1:], 0)
                    char_raid = profile_data["raid_progression"][
                        "sepulcher-of-the-first-ones"
                    ]["summary"]
                    char_last_updated = self._parse_date(
                        profile_data["last_crawled_at"]
                    )
                    char_ilvl = profile_data["gear"]["item_level_equipped"]
                    char_covenant = profile_data["covenant"]["name"]
                    char_url = profile_data["profile_url"]

                    banner = profile_data["profile_banner"]

                    banner_url = f"https://cdnassets.raider.io/images/profile/masthead_backdrops/v2/{banner}.jpg"
                    armory_url = f"https://worldofwarcraft.com/en-gb/character/eu/{realm}/{char_name}"
                    wcl_url = (
                        f"https://www.warcraftlogs.com/character/eu/{realm}/{char_name}"
                    )
                    raidbots_url = f"https://www.raidbots.com/simbot/quick?region=eu&realm={realm}&name={char_name}"

                    embed = discord.Embed(
                        title=char_name,
                        url=char_url,
                        description=f"{char_race} {char_spec} {char_class}",
                        color=char_score_color,
                    )
                    embed.set_author(
                        name=_("Raider.io profile"),
                        icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg",
                    )
                    embed.set_thumbnail(url=char_image)
                    embed.add_field(
                        name=_("__**Mythic+ Score**__"),
                        value=char_score["score"],
                        inline=False,
                    )
                    embed.add_field(
                        name=_("Raid progress"), value=char_raid, inline=True
                    )
                    embed.add_field(name=_("Item level"), value=char_ilvl, inline=True)
                    embed.add_field(
                        name=_("Covenant"), value=char_covenant, inline=True
                    )
                    embed.add_field(
                        name=_("__Other links__"),
                        value=_(
                            "[Armory]({armory_url}) | [WarcraftLogs]({wcl_url}) | [Raidbots]({raidbots_url})"
                        ).format(
                            armory_url=armory_url,
                            wcl_url=wcl_url,
                            raidbots_url=raidbots_url,
                        ),
                    )
                    embed.set_image(url=banner_url)
                    embed.set_footer(
                        text=_("Last updated: {char_last_updated}").format(
                            char_last_updated=char_last_updated
                        )
                    )

                    await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @raiderio.command(name="guild")
    async def raiderio_guild(self, ctx, guild: str, *realm: str) -> None:
        """Display the raider.io profile of a guild.

        If the guild or realm name have spaces in them, they need to be enclosed in quotes.

        Example:
        [p]raiderio guild "Jahaci Rumene Kadulje" Ragnaros
        """
        async with ctx.typing():
            region: str = await self.config.region()
            if not realm:
                realm: str = await self.config.guild(ctx.guild).realm()
            try:
                if not region:
                    raise ValueError(
                        _(
                            "\nThe bot owner needs to set a region with `[p]wowset region` first."
                        )
                    )
                if not realm:
                    raise ValueError(
                        _(
                            "A server admin needs to set a realm with `[p]wowset realm` first."
                        )
                    )
                async with RaiderIO() as rio:
                    profile_data = await rio.get_guild_profile(
                        region,
                        realm,
                        guild,
                        fields=["raid_rankings", "raid_progression"],
                    )

                    guild_name: str = profile_data["name"]
                    guild_url: str = profile_data["profile_url"]
                    last_updated: str = self._parse_date(
                        profile_data["last_crawled_at"]
                    )

                    ranks = (
                        profile_data["raid_rankings"]["sepulcher-of-the-first-ones"][
                            "normal"
                        ],
                        profile_data["raid_rankings"]["sepulcher-of-the-first-ones"][
                            "heroic"
                        ],
                        profile_data["raid_rankings"]["sepulcher-of-the-first-ones"][
                            "mythic"
                        ],
                    )
                    difficulties = ("Normal", "Heroic", "Mythic")

                    raid_progression: str = profile_data["raid_progression"][
                        "sepulcher-of-the-first-ones"
                    ]["summary"]

                    embed = discord.Embed(
                        title=guild_name, url=guild_url, color=0xFF2121
                    )
                    embed.set_author(
                        name=_("Guild profile"),
                        icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg",
                    )
                    embed.add_field(
                        name=_("__**Progress**__"), value=raid_progression, inline=False
                    )

                    for rank, difficulty in zip(ranks, difficulties):
                        world = rank["world"]
                        region = rank["region"]
                        realm = rank["realm"]

                        embed.add_field(
                            name=_("{difficulty} rank").format(difficulty=difficulty),
                            value=_(
                                "World: {world}\nRegion: {region}\nRealm: {realm}"
                            ).format(world=world, region=region, realm=realm),
                        )

                    embed.set_footer(
                        text=_("Last updated: {last_updated}").format(
                            last_updated=last_updated
                        )
                    )

                    await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @raiderio.command(name="scoreboard", aliases=["sb"])
    async def raiderio_scoreboard(self, ctx: commands.Context):
        """Show the Mythic+ rating leaderboard of your guild."""
        async with ctx.typing():
            embed = await self._generate_scoreboard(ctx)
        await ctx.send(embed=embed)

    @commands.group()
    async def sbset(self, ctx):
        """Change scoreboard settings"""
        pass

    @sbset.command(name="channel")
    @commands.admin()
    async def sbset_channel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Set the channel to send the scoreboard to."""
        sb_channel_id: int = await self.config.guild(ctx.guild).scoreboard_channel()
        sb_msg_id: int = await self.config.guild(ctx.guild).scoreboard_message()
        if not channel:
            if sb_msg_id:  # Remove the scoreboard message if it exists
                await self._delete_scoreboard(
                    ctx,
                    sb_channel_id,
                    sb_msg_id,
                )
            await self.config.guild(ctx.guild).scoreboard_channel.clear()
            await self.config.guild(ctx.guild).scoreboard_message.clear()
            await ctx.send(_("Scoreboard channel cleared."))
            return
        if sb_msg_id:  # Remove the old scoreboard
            await self._delete_scoreboard(
                ctx,
                sb_channel_id,
                sb_msg_id,
            )
        await self.config.guild(ctx.guild).scoreboard_channel.set(channel.id)
        embed = await self._generate_scoreboard(ctx)
        sb_msg = await channel.send(embed=embed)
        await self.config.guild(ctx.guild).scoreboard_message.set(sb_msg.id)
        await ctx.send(_("Scoreboard channel set."))

    @staticmethod
    async def get_formatted_top_scores(
        guild_name: str, max_chars: int, realm: str, region: str
    ):
        async with RaiderIO() as rio:
            roster = await rio.get_guild_roster(region, realm, guild_name)

            lb = {}
            # TODO: Surely there's a better way to do literally everything below
            for char in roster["guildRoster"]["roster"]:
                char_name = char["character"]["name"]
                score = char["keystoneScores"]["allScore"]

                if score > 250:
                    lb[char_name] = score

            lb = dict(sorted(lb.items(), key=lambda i: i[1], reverse=True))

            chars = list(lb.keys())[:max_chars]
            scores = list(lb.values())[:max_chars]

            tabulate_list = []
            for index, char_info in enumerate(zip(chars, scores)):
                char_name = char_info[0]
                char_score = char_info[1]
                tabulate_list.append(
                    [
                        f"{index + 1}.",
                        char_name,
                        humanize_number(int(char_score)),
                    ]
                )
        return tabulate_list

    @tasks.loop(minutes=5)
    async def update_scoreboard(self):
        for guild in self.bot.guilds:
            sb_channel_id: int = await self.config.guild(guild).scoreboard_channel()
            sb_msg_id: int = await self.config.guild(guild).scoreboard_message()
            if sb_channel_id and sb_msg_id:
                sb_channel: discord.TextChannel = guild.get_channel(sb_channel_id)
                sb_msg: discord.Message = await sb_channel.fetch_message(sb_msg_id)
                if sb_msg:
                    max_chars = 20
                    headers = ["#", _("Name"), _("Score")]
                    region: str = await self.config.region()
                    realm: str = await self.config.guild(guild).realm()
                    guild_name: str = await self.config.guild(guild).real_guild_name()
                    if not region:
                        raise ValueError(
                            _(
                                "\nThe bot owner needs to set a region with `[p]wowset region` first."
                            )
                        )
                    if not realm:
                        raise ValueError(
                            _(
                                "\nA server admin needs to set a realm with `[p]wowset realm` first."
                            )
                        )
                    if not guild_name:
                        raise ValueError(
                            _(
                                "\nA server admin needs to set a guild name with `[p]wowset guild` first."
                            )
                        )

                    embed = discord.Embed(
                        title=_("Mythic+ Guild Scoreboard"),
                        color=await self.bot.get_embed_color(sb_msg),
                    )
                    embed.set_author(name=guild.name, icon_url=guild.icon_url)
                    tabulate_list = await self.get_formatted_top_scores(
                        guild_name, max_chars, realm, region
                    )

                    embed.description = box(
                        tabulate(
                            tabulate_list,
                            headers=headers,
                            tablefmt="plain",
                            disable_numparse=True,
                        ),
                        lang="md",
                    )
                    # Don't edit if there wouldn't be a change
                    if sb_msg.embeds[0].description == embed.description:
                        return
                    await sb_msg.edit(embed=embed)

    async def _generate_scoreboard(self, ctx: commands.Context) -> discord.Embed:
        max_chars = 20
        headers = ["#", _("Name"), _("Score")]
        region: str = await self.config.region()
        realm: str = await self.config.guild(ctx.guild).realm()
        guild_name: str = await self.config.guild(ctx.guild).real_guild_name()
        try:
            if not region:
                raise ValueError(
                    _(
                        "\nThe bot owner needs to set a region with `[p]wowset region` first."
                    )
                )
            if not realm:
                raise ValueError(
                    _(
                        "\nA server admin needs to set a realm with `[p]wowset realm` first."
                    )
                )
            if not guild_name:
                raise ValueError(
                    _(
                        "\nA server admin needs to set a guild name with `[p]wowset guild` first."
                    )
                )

            embed = discord.Embed(
                title=_("Mythic+ Guild Scoreboard"),
                color=await ctx.embed_color(),
            )
            embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
            tabulate_list = await self.get_formatted_top_scores(
                guild_name, max_chars, realm, region
            )

            embed.description = box(
                tabulate(
                    tabulate_list,
                    headers=headers,
                    tablefmt="plain",
                    disable_numparse=True,
                ),
                lang="md",
            )
            return embed
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))

    @staticmethod
    async def _delete_scoreboard(
        ctx: commands.Context, sb_channel_id: int, sb_msg_id: int
    ):
        try:
            sb_channel: discord.TextChannel = ctx.guild.get_channel(sb_channel_id)
            sb_msg: discord.Message = await sb_channel.fetch_message(sb_msg_id)
        except discord.NotFound:
            sb_msg = None  # TODO: Log this. Message or channel were already deleted or don't exist for some reason.
        if sb_msg:
            await sb_msg.delete()

    @staticmethod
    def _parse_date(tz_date) -> str:
        parsed = isoparse(tz_date) + timedelta(hours=2)
        formatted = parsed.strftime("%d/%m/%y - %H:%M:%S")
        return formatted
