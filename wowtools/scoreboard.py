import io
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

import discord
from aiohttp import ClientResponseError
from discord.ext import tasks
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont
from raiderio_async import RaiderIO
from redbot.core import commands
from redbot.core.data_manager import bundled_data_path
from redbot.core.i18n import Translator, set_contextual_locales_from_guild
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number
from tabulate import tabulate

from .utils import get_api_client

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)

DEV_GUILDS = [362298824854863882, 133049272517001216]


class Scoreboard:
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    @commands.hybrid_group(name="wowscoreboard", aliases=["sb"])
    @commands.guild_only()
    async def wowscoreboard(self, ctx: commands.Context):
        """Show various scoreboards for your guild."""
        pass

    @wowscoreboard.command(name="dungeon")
    @commands.guild_only()
    async def wowscoreboard_dungeon(self, ctx: commands.Context):
        """Get the Mythic+ scoreboard for this guild."""
        if ctx.interaction:
            # There is no contextual locale for interactions, so we need to set it manually
            # (This is probably a bug in Red, remove this when it's fixed)
            await set_contextual_locales_from_guild(self.bot, ctx.guild)

        image_enabled = await self.config.guild(ctx.guild).sb_image()
        try:
            if image_enabled:
                await ctx.defer()
                embed, img_file = await self._generate_dungeon_scoreboard(ctx, True)
            else:
                embed = await self._generate_dungeon_scoreboard(ctx)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))
            return
        if embed:
            if image_enabled:
                await ctx.send(embed=embed, file=img_file)
            else:
                await ctx.send(embed=embed)

    @commands.cooldown(rate=1, per=60, type=commands.BucketType.guild)
    @wowscoreboard.command(name="pvp", hidden=True)
    @commands.guild_only()
    async def wowscoreboard_pvp(self, ctx: commands.Context):
        """Get all the PvP related scoreboards for this guild.

        **Characters that have not played all PvP gamemodes at
        some point will not be shown.**
        """
        if ctx.interaction:
            # There is no contextual locale for interactions, so we need to set it manually
            # (This is probably a bug in Red, remove this when it's fixed)
            await set_contextual_locales_from_guild(self.bot, ctx.guild)

        embed = await self._generate_pvp_scoreboard(ctx)
        if embed:
            # TODO: In dpy2, make this a list of embeds to send in a single message
            await ctx.send(embed=embed)

    @commands.group()
    @commands.admin()
    @commands.guild_only()
    async def sbset(self, ctx):
        """Change scoreboard settings"""
        pass

    @sbset.command(name="channel")
    @commands.admin()
    @commands.guild_only()
    async def sbset_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set the channel to send the scoreboard to."""
        image_enabled = await self.config.guild(ctx.guild).sb_image()
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
        try:
            if image_enabled:
                embed, img_file = await self._generate_dungeon_scoreboard(ctx, image=True)
            else:
                embed = await self._generate_dungeon_scoreboard(ctx)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))
            return
        if image_enabled:
            sb_msg = await channel.send(file=img_file, embed=embed)
        else:
            sb_msg = await channel.send(embed=embed)
        await self.config.guild(ctx.guild).scoreboard_message.set(sb_msg.id)
        await ctx.send(_("Scoreboard channel set."))

    @sbset.group(name="blacklist", aliases=["blocklist"])
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist(self, ctx: commands.Context):
        """Manage the scoreboard blacklist."""
        pass

    @sbset_blacklist.command(name="add")
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist_add(self, ctx: commands.Context, *, characters: str):
        """Add characters to the scoreboard blacklist.

        Characters can be separated by spaces or commas.
        """
        blacklist: List[str] = await self.config.guild(ctx.guild).scoreboard_blacklist()
        for character in characters.split(" "):
            character = character.strip(",")
            if character not in blacklist:
                blacklist.append(character.lower())
        await self.config.guild(ctx.guild).scoreboard_blacklist.set(blacklist)
        await ctx.send(_("Blacklisted characters added."))

    @sbset_blacklist.command(name="remove")
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist_remove(self, ctx: commands.Context, *, characters: str):
        """Remove characters from the scoreboard blacklist.

        Characters can be separated by spaces or commas.
        """
        blacklist: List[str] = await self.config.guild(ctx.guild).scoreboard_blacklist()
        for character in characters.split(" "):
            character = character.strip(",")
            character = character.lower()
            if character in blacklist:
                blacklist.remove(character.lower())
        await self.config.guild(ctx.guild).scoreboard_blacklist.set(blacklist)
        await ctx.send(_("Blacklisted characters removed."))

    @sbset_blacklist.command(name="list")
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist_list(self, ctx: commands.Context):
        """List the characters on the scoreboard blacklist."""
        blacklist: List[str] = await self.config.guild(ctx.guild).scoreboard_blacklist()
        if not blacklist:
            await ctx.send(_("No characters are blacklisted."))
            return
        await ctx.send(
            _("Blacklisted characters: {characters}").format(characters=humanize_list(blacklist))
        )

    @sbset_blacklist.command(name="clear")
    @commands.admin()
    @commands.guild_only()
    async def sbset_blacklist_clear(self, ctx: commands.Context):
        """Clear the scoreboard blacklist."""
        await self.config.guild(ctx.guild).scoreboard_blacklist.clear()
        await ctx.send(_("Blacklisted characters cleared."))

    @sbset.command(name="lock", hidden=True)
    @commands.admin()
    @commands.guild_only()
    async def sbset_lock(self, ctx: commands.Context):
        """Lock the current scoreboard and does not update it anymore."""
        sb_channel_id: int = await self.config.guild(ctx.guild).scoreboard_channel()
        sb_msg_id: int = await self.config.guild(ctx.guild).scoreboard_message()
        if not (sb_channel_id and sb_msg_id):
            await ctx.send(_("No scoreboard is set."))
            return

        sb_channel = ctx.guild.get_channel(sb_channel_id)
        try:
            sb_msg = await sb_channel.fetch_message(sb_msg_id)
        except discord.HTTPException:
            await ctx.send(_("Failed to fetch scoreboard message."))
            return

        embed = sb_msg.embeds[0]
        embed.title = _("Season 1 Mythic+ Scoreboard")
        embed.description = _("Dragonflight Season 1 has ended.\nThis scoreboard is final.")
        embed.set_footer(text=_("This scoreboard is locked."))
        await sb_msg.edit(embed=embed, attachments=[])

        await self.config.guild(ctx.guild).scoreboard_channel.clear()
        await self.config.guild(ctx.guild).scoreboard_message.clear()
        await ctx.send(_("Scoreboard locked."))

    @tasks.loop(minutes=5)
    async def update_dungeon_scoreboard(self):
        for guild in self.bot.guilds:
            if await self.bot.cog_disabled_in_guild(self, guild):
                continue
            await set_contextual_locales_from_guild(self.bot, guild)

            sb_channel_id: int = await self.config.guild(guild).scoreboard_channel()
            sb_msg_id: int = await self.config.guild(guild).scoreboard_message()
            if not (sb_channel_id and sb_msg_id):
                continue
            sb_channel: discord.TextChannel = guild.get_channel(sb_channel_id)

            try:
                sb_msg: discord.Message = await sb_channel.fetch_message(sb_msg_id)
            except discord.HTTPException:
                log.error(
                    f"Failed to fetch scoreboard message in guild {guild.id} ({guild.name}).",
                    exc_info=True,
                )
                continue
            if not sb_msg:
                continue

            max_chars = 20
            headers = ["#", _("Name"), _("Score")]
            region: str = await self.config.guild(guild).region()
            realm: str = await self.config.guild(guild).realm()
            guild_name: str = await self.config.guild(guild).real_guild_name()
            sb_blacklist: List[str] = await self.config.guild(guild).scoreboard_blacklist()
            if not region or not realm or not guild_name:
                continue
            image: bool = await self.config.guild(guild).sb_image()

            embed = discord.Embed(
                title=_("Mythic+ Guild Scoreboard"),
                color=await self.bot.get_embed_color(sb_msg),
            )
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
            try:
                tabulate_list = await self._get_dungeon_scores(
                    guild_name,
                    max_chars,
                    realm,
                    region,
                    sb_blacklist,
                    image=image,
                )
            except ValueError as e:
                log.error(f"Error getting dungeon scores for {guild.id}, skipping. Response: {e}")
                continue

            # TODO: When dpy2 is out, use discord.utils.format_dt()
            desc = _("Last updated <t:{timestamp}:R>\n").format(
                timestamp=int(datetime.now(timezone.utc).timestamp())
            )
            desc += _("Score cutoff for season title: `{cutoff}`").format(
                cutoff=await self.get_season_title_cutoff(region)
            )

            if image:
                img_file = await self._generate_scoreboard_image(
                    tabulate_list, dev_guild=guild.id in DEV_GUILDS
                )
                embed.set_image(url=f"attachment://{img_file.filename}")
                embed.set_footer(text=_("Updates every 5 minutes"))
            else:
                formatted_rankings = box(
                    tabulate(
                        tabulate_list,
                        headers=headers,
                        tablefmt="plain",
                        disable_numparse=True,
                    ),
                    lang="md",
                )
                desc += formatted_rankings

                # Don't edit if there wouldn't be a change
                old_rankings = sb_msg.embeds[0].description.splitlines()
                old_rankings = "\n".join(old_rankings[1:])
                if old_rankings == formatted_rankings:
                    continue
                embed.set_footer(text=_("Updates only when there is a ranking change"))

            ass_integration = await self.config.assistant_cog_integration()
            if (assistant := self.bot.get_cog("Assistant")) and ass_integration:
                await self.add_assistant_embedding(assistant, guild, image, tabulate_list)

            embed.description = desc

            try:
                if image:
                    await sb_msg.edit(embed=embed, attachments=[img_file])
                else:
                    await sb_msg.edit(embed=embed, attachments=[])
            except discord.Forbidden:
                log.error(
                    f"Failed to edit scoreboard message in guild {guild.id} ({guild.name}) "
                    f"due to missing permissions.",
                    exc_info=True,
                )
            except discord.HTTPException:
                log.error(
                    f"Failed to edit scoreboard message in guild {guild.id} ({guild.name}).",
                    exc_info=True,
                )

    @staticmethod
    async def add_assistant_embedding(assistant, guild, image, tabulate_list):
        if image:
            formatted_tab_list = [char[:3] + [char[-1]] for char in tabulate_list]
        headers = ["#", " | Name", " | Score", " | Item level"]
        formatted_rankings = (
            "This is a Mythic+ Guild Scoreboard, generated by you. " "It is sorted by score.\n\n"
        )
        formatted_rankings += tabulate(
            formatted_tab_list if image else tabulate_list,
            headers=headers,
            tablefmt="plain",
            disable_numparse=True,
        )
        try:
            await assistant.add_embedding(guild, "wowtools_scoreboard", formatted_rankings, True)
        except Exception as e:
            log.error(f"Error adding scoreboard to Assistant: {e}", exc_info=True)

    @staticmethod
    async def get_season_title_cutoff(region: str) -> float:
        current_season = "season-df-2"  # TODO: Needs to be manually updated every season
        async with RaiderIO() as rio:
            cutoffs = (await rio.get_mythic_plus_season_cutoffs(region, current_season)).get(
                "cutoffs"
            )
        return cutoffs["p999"]["all"]["quantileMinValue"]

    @update_dungeon_scoreboard.error
    async def update_dungeon_scoreboard_error(self, error):
        # Thanks Flame!
        log.error(f"Unhandled error in update_dungeon_scoreboard task: {error}", exc_info=True)

    @staticmethod
    async def _get_dungeon_scores(
        guild_name: str,
        max_chars: int,
        realm: str,
        region: str,
        sb_blacklist: List[str],
        image: bool,
    ):
        async with RaiderIO() as rio:
            roster = await rio.get_guild_roster(region, realm, guild_name)
            if "error" in roster.keys():
                raise ValueError(f"{roster['message']}.")

            lb = {}
            # TODO: Surely there's a better way to do literally everything below
            for char in roster["guildRoster"]["roster"]:
                char_name: str = char["character"]["name"]
                if any(char.isdigit() for char in char_name):
                    continue

                score = char["keystoneScores"]["allScore"]

                if score > 250 and char_name.lower() not in sb_blacklist:
                    if image:
                        class_color: str = ClassColor.get_class_color(
                            char["character"]["class"]["name"]
                        )
                        char_img: str = (
                            "https://render.worldofwarcraft.com/{region}/character/{}".format(
                                char["character"]["thumbnail"], region=region
                            )
                        )
                        ilvl = str(char["character"]["items"]["item_level_equipped"])
                        score_color: str = char["keystoneScores"]["allScoreColor"]
                        lb[char_name] = (score, score_color, char_img, class_color, ilvl)
                    else:
                        lb[char_name] = score

            lb = dict(sorted(lb.items(), key=lambda i: i[1], reverse=True))

            chars = list(lb.keys())[:max_chars]
            scores = list(lb.values())[:max_chars]

            tabulate_list = []
            for index, char_info in enumerate(zip(chars, scores)):
                char_name = char_info[0]
                if image:
                    char_score = char_info[1][0]
                    char_score_color = char_info[1][1]
                    char_img = char_info[1][2]
                    class_color = char_info[1][3]
                    ilvl = char_info[1][4]
                    tabulate_list.append(
                        [
                            f"{index + 1}.",
                            char_name,
                            str(int(char_score)),
                            char_score_color,
                            char_img,
                            class_color,
                            ilvl,
                        ]
                    )
                else:
                    char_score = char_info[1]
                    tabulate_list.append(
                        [
                            f"{index + 1}.",
                            char_name,
                            humanize_number(int(char_score)),
                        ]
                    )

        return tabulate_list

    async def _generate_dungeon_scoreboard(self, ctx: commands.Context, image: bool = False):
        max_chars = 20
        headers = ["#", _("Name"), _("Score")]
        guild_name, realm, region, sb_blacklist = await self._get_guild_config(ctx)
        if not region:
            raise ValueError(
                _(
                    "\nA server admin needs to set a region with `{prefix}wowset region` first."
                ).format(prefix="" if ctx.interaction else ctx.clean_prefix)
            )
        if not realm:
            raise ValueError(
                _(
                    "\nA server admin needs to set a realm with `{prefix}wowset realm` first."
                ).format(prefix="" if ctx.interaction else ctx.clean_prefix)
            )
        if not guild_name:
            raise ValueError(
                _(
                    "\nA server admin needs to set a guild name with `{prefix}wowset guild` first."
                ).format(prefix="" if ctx.interaction else ctx.clean_prefix)
            )

        embed = discord.Embed(
            title=_("Mythic+ Guild Scoreboard"),
            color=await ctx.embed_color(),
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)

        tabulate_list = await self._get_dungeon_scores(
            guild_name, max_chars, realm, region, sb_blacklist, image
        )

        if image:
            img_file = await self._generate_scoreboard_image(
                tabulate_list, dev_guild=ctx.guild.id in DEV_GUILDS
            )
            embed.set_image(url=f"attachment://{img_file.filename}")
            return embed, img_file
        else:
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

    async def _generate_scoreboard_image(self, tabulate_list: list, dev_guild: bool = False):
        img_path = str(
            bundled_data_path(self) / "scoreboard-df-s2-jrk.png"
            if dev_guild
            else bundled_data_path(self) / "scoreboard-df-s1.png"
        )
        img = Image.open(img_path)
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(str(bundled_data_path(self) / "Roboto-Bold.ttf"), 28)

        x = 150
        y = 100 if dev_guild else 25

        for character in tabulate_list[:10]:
            char_name = character[1]
            score = character[2]
            ilvl = character[6]

            score_color = ImageColor.getcolor(character[3], "RGB")
            class_color = ImageColor.getcolor(character[5], "RGB")
            ilvl_color = self._get_ilvl_color(int(ilvl))

            async with self.session.request("GET", character[4]) as resp:
                image = await resp.content.read()
                image = Image.open(io.BytesIO(image))
                image = image.resize((65, 65))
                img.paste(image, (x - 79, y - 15))

            draw.text((x, y), char_name, class_color, font=font)
            if ilvl_color == "#FF69B4":  # This is whatever the color for the highest ilvl is
                glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
                ImageDraw.Draw(glow).text((x + 225, y), ilvl, ilvl_color, font=font)
                blurred_glow = glow.filter(ImageFilter.GaussianBlur(5))
                ImageDraw.Draw(blurred_glow).text((x + 225, y), ilvl, ilvl_color, font=font)
                img = Image.alpha_composite(img, blurred_glow)
                # have to reassing draw
                draw = ImageDraw.Draw(img)
            else:
                draw.text((x + 225, y), ilvl, ilvl_color, font=font)
            draw.text((x + 300, y), score, score_color, font=font)
            y += 75

        img_obj = io.BytesIO()
        img.save(img_obj, format="PNG")
        img_obj.seek(0)

        return discord.File(fp=img_obj, filename="scoreboard.png")

    @staticmethod
    def _get_ilvl_color(ilvl: int) -> str:
        if ilvl >= 446:
            return "#f16960"
        elif ilvl >= 443:
            return "#FF69B4"
        elif ilvl >= 440:
            return "#FFA500"
        elif ilvl >= 435:
            return "#b040c2"
        elif ilvl >= 430:
            return "#445bc2"
        elif ilvl >= 425:
            return "#00ff1a"
        else:
            return "#FFFFFF"

    @staticmethod
    async def _delete_scoreboard(ctx: commands.Context, sb_channel_id: int, sb_msg_id: int):
        try:
            sb_channel: discord.TextChannel = ctx.guild.get_channel(sb_channel_id)
            sb_msg: discord.Message = await sb_channel.fetch_message(sb_msg_id)
        except discord.NotFound:
            sb_msg = None
            log.info(f"Scoreboard message in {ctx.guild} ({ctx.guild.id}) not found.")
        if sb_msg:
            await sb_msg.delete()

    async def _generate_pvp_scoreboard(self, ctx: commands.Context) -> Optional[discord.Embed]:
        max_chars = 10
        headers = ["#", _("Name"), _("Rating")]
        guild_name, realm, region, sb_blacklist = await self._get_guild_config(ctx)
        if not region:
            await ctx.send(
                _(
                    "\nA server admin needs to set a region with `{prefix}wowset region` first."
                ).format(prefix="" if ctx.interaction else ctx.clean_prefix)
            )
            return None
        if not realm:
            await ctx.send(
                _(
                    "\nA server admin needs to set a realm with `{prefix}wowset realm` first."
                ).format(prefix="" if ctx.interaction else ctx.clean_prefix)
            )
            return None
        if not guild_name:
            await ctx.send(
                _(
                    "\nA server admin needs to set a guild name with `{prefix}wowset guild` first."
                ).format(prefix="" if ctx.interaction else ctx.clean_prefix)
            )
            return None

        msg = await ctx.send(
            _("Fetching scoreboard...\n" "This can take up to 30 minutes for very large guilds.")
        )

        embed_pvp = discord.Embed(
            title=_("Guild PvP Leaderboard"),
            color=await ctx.embed_color(),
        )

        tabulate_lists = await self._get_pvp_scores(
            ctx, guild_name, max_chars, realm, region, sb_blacklist
        )
        if not tabulate_lists:
            await msg.delete()
            return None

        embed_pvp.add_field(
            name=_("RBG Leaderboard"),
            value=box(
                tabulate(
                    tabulate_lists[0],
                    headers=headers,
                    tablefmt="plain",
                    disable_numparse=True,
                ),
                lang="md",
            ),
            inline=False,
        )
        embed_pvp.add_field(
            name=_("2v2 Arena Leaderboard"),
            value=box(
                tabulate(
                    tabulate_lists[1],
                    headers=headers,
                    tablefmt="plain",
                    disable_numparse=True,
                ),
                lang="md",
            ),
            inline=False,
        )
        embed_pvp.add_field(
            name=_("3v3 Arena Leaderboard"),
            value=box(
                tabulate(
                    tabulate_lists[2],
                    headers=headers,
                    tablefmt="plain",
                    disable_numparse=True,
                ),
                lang="md",
            ),
            inline=False,
        )

        await msg.delete()
        return embed_pvp

    async def _get_pvp_scores(
        self,
        ctx,
        guild_name: str,
        max_chars: int,
        realm: str,
        region: str,
        sb_blacklist: List[str],
    ) -> list:
        try:
            api_client = await get_api_client(self.bot, region)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))
            return []
        guild_name = guild_name.replace(" ", "-").lower()

        max_level = 70
        async with api_client as client:
            wow_client = client.Retail
            # await self.limiter.acquire()
            current_season: int = (await wow_client.GameData.get_pvp_seasons_index())[
                "current_season"
            ]["id"]

            # await self.limiter.acquire()
            try:
                guild_roster = await wow_client.Profile.get_guild_roster(
                    name_slug=guild_name, realm_slug=realm
                )
            except ClientResponseError:
                await ctx.send(_("Guild not found."))
                return []

            roster = {"rbg": {}, "2v2": {}, "3v3": {}}

            for member in guild_roster["members"]:
                character_name = member["character"]["name"].lower()
                if character_name in sb_blacklist:
                    continue
                if member["character"]["level"] < max_level:
                    continue

                log.debug(f"Getting PvP data for {character_name}")
                try:
                    (
                        rbg_statistics,
                        duo_statistics,
                        tri_statistics,
                    ) = await client.multi_request(
                        [
                            wow_client.Profile.get_character_pvp_bracket_statistics(
                                character_name=character_name,
                                realm_slug=realm,
                                pvp_bracket="rbg",
                            ),
                            wow_client.Profile.get_character_pvp_bracket_statistics(
                                character_name=character_name,
                                realm_slug=realm,
                                pvp_bracket="2v2",
                            ),
                            wow_client.Profile.get_character_pvp_bracket_statistics(
                                character_name=character_name,
                                realm_slug=realm,
                                pvp_bracket="3v3",
                            ),
                        ]
                    )
                except ClientResponseError:
                    continue

                if "rating" in rbg_statistics and rbg_statistics["season"]["id"] == current_season:
                    roster["rbg"][character_name] = rbg_statistics["rating"]
                    log.debug(f"{character_name} has RBG rating {rbg_statistics['rating']}")
                if "rating" in duo_statistics and duo_statistics["season"]["id"] == current_season:
                    roster["2v2"][character_name] = duo_statistics["rating"]
                    log.debug(f"{character_name} has 2v2 rating {duo_statistics['rating']}")
                if "rating" in tri_statistics and tri_statistics["season"]["id"] == current_season:
                    roster["3v3"][character_name] = tri_statistics["rating"]
                    log.debug(f"{character_name} has 3v3 rating {tri_statistics['rating']}")

        roster["rbg"] = dict(sorted(roster["rbg"].items(), key=lambda i: i[1], reverse=True))
        roster["2v2"] = dict(sorted(roster["2v2"].items(), key=lambda i: i[1], reverse=True))
        roster["3v3"] = dict(sorted(roster["3v3"].items(), key=lambda i: i[1], reverse=True))

        return await self._make_tabulate_lists(max_chars, roster)

    @staticmethod
    async def _make_tabulate_lists(max_chars, roster):
        characters_rbg = list(roster["rbg"].keys())[:max_chars]
        characters_2v2 = list(roster["2v2"].keys())[:max_chars]
        characters_3v3 = list(roster["3v3"].keys())[:max_chars]
        ratings_rbg = list(roster["rbg"].values())[:max_chars]
        ratings_2v2 = list(roster["2v2"].values())[:max_chars]
        ratings_3v3 = list(roster["3v3"].values())[:max_chars]

        tabulate_lists = [[], [], []]  # [RBG, 2v2, 3v3]
        await Scoreboard._make_rbg_tabulate_list(characters_rbg, ratings_rbg, tabulate_lists)
        await Scoreboard._make_2v2_tabulate_list(characters_2v2, ratings_2v2, tabulate_lists)
        await Scoreboard._make_3v3_tabulate_list(characters_3v3, ratings_3v3, tabulate_lists)
        return tabulate_lists

    @staticmethod
    async def _make_3v3_tabulate_list(characters_3v3, ratings_3v3, tabulate_lists):
        for index, char_info in enumerate(zip(characters_3v3, ratings_3v3)):
            char_name: str = char_info[0]
            char_rating: int = char_info[1]
            tabulate_lists[2].append(
                [
                    f"{index + 1}.",
                    char_name.capitalize(),
                    humanize_number(char_rating),
                ]
            )

    @staticmethod
    async def _make_2v2_tabulate_list(characters_2v2, ratings_2v2, tabulate_lists):
        for index, char_info in enumerate(zip(characters_2v2, ratings_2v2)):
            char_name: str = char_info[0]
            char_rating: int = char_info[1]
            tabulate_lists[1].append(
                [
                    f"{index + 1}.",
                    char_name.capitalize(),
                    humanize_number(char_rating),
                ]
            )

    @staticmethod
    async def _make_rbg_tabulate_list(characters_rbg, ratings_rbg, tabulate_lists):
        for index, char_info in enumerate(zip(characters_rbg, ratings_rbg)):
            char_name: str = char_info[0]
            char_rating: int = char_info[1]
            tabulate_lists[0].append(
                [
                    f"{index + 1}.",
                    char_name.capitalize(),
                    humanize_number(char_rating),
                ]
            )

    async def _get_guild_config(self, ctx):
        region: str = await self.config.guild(ctx.guild).region()
        realm: str = await self.config.guild(ctx.guild).realm()
        guild_name: str = await self.config.guild(ctx.guild).real_guild_name()
        sb_blacklist: List[str] = await self.config.guild(ctx.guild).scoreboard_blacklist()
        return guild_name, realm, region, sb_blacklist


class ClassColor(Enum):
    DEATH_KNIGHT = "#C41F3B"
    DEMON_HUNTER = "#A330C9"
    DRUID = "#FF7D0A"
    HUNTER = "#ABD473"
    MAGE = "#69CCF0"
    MONK = "#00FF96"
    PALADIN = "#F58CBA"
    PRIEST = "#FFFFFF"
    ROGUE = "#FFF569"
    SHAMAN = "#0070DE"
    WARLOCK = "#9482C9"
    WARRIOR = "#C79C6E"
    EVOKER = "#1F594D"

    @staticmethod
    def get_class_color(player_class: str) -> str:
        try:
            return ClassColor[player_class.upper().replace(" ", "_")].value
        except KeyError:
            return "#FFFFFF"
