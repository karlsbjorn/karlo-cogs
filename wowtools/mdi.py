import io
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import tasks
from PIL import Image, ImageDraw, ImageFont
from raiderio_async import RaiderIO
from redbot.core import commands
from redbot.core.data_manager import bundled_data_path
from redbot.core.i18n import Translator, set_contextual_locales_from_guild

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("WoWTools", __file__)


class MDI:
    @commands.group()
    @commands.admin()
    @commands.guild_only()
    async def mdiset(self, ctx: commands.Context):
        """MDI postavke."""
        pass

    @mdiset.command(name="channel")
    @commands.admin()
    @commands.guild_only()
    async def mdiset_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Postavi kanal za MDI ljestvicu."""
        mdi_channel_id: int = await self.config.guild(ctx.guild).mdi_channel()
        mdi_msg_id: int = await self.config.guild(ctx.guild).mdi_message()
        if not channel:
            if mdi_channel_id:  # Remove the scoreboard message if it exists
                await self._delete_scoreboard(
                    ctx,
                    mdi_channel_id,
                    mdi_msg_id,
                )
            await self.config.guild(ctx.guild).mdi_channel.clear()
            await self.config.guild(ctx.guild).mdi_message.clear()
            await ctx.send(_("Scoreboard channel cleared."))
            return
        if mdi_msg_id:  # Remove the old scoreboard
            await self._delete_scoreboard(
                ctx,
                mdi_channel_id,
                mdi_msg_id,
            )
        await self.config.guild(ctx.guild).mdi_channel.set(channel.id)
        try:
            embed, img_file = await self._generate_mdi_scoreboard(ctx)
        except Exception as e:
            await ctx.send(_("Command failed successfully. {e}").format(e=e))
            return
        sb_msg = await channel.send(file=img_file, embed=embed)
        await self.config.guild(ctx.guild).mdi_message.set(sb_msg.id)
        await ctx.send("Kanal za MDI ljestvicu postavljen.")

    @staticmethod
    async def _delete_scoreboard(ctx: commands.Context, sb_channel_id: int, sb_msg_id: int):
        try:
            sb_channel: discord.TextChannel = ctx.guild.get_channel(sb_channel_id)
            sb_msg: discord.Message = await sb_channel.fetch_message(sb_msg_id)
        except discord.NotFound:
            log.info(f"Scoreboard message in {ctx.guild} ({ctx.guild.id}) not found.")
            return
        if sb_msg:
            await sb_msg.delete()

    async def _generate_mdi_scoreboard(self, ctx: commands.Context):
        embed = discord.Embed(
            title="MDI timovi",
            color=await ctx.embed_color(),
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
        img_file = await self._generate_mdi_image()
        embed.set_image(url=f"attachment://{img_file.filename}")
        return embed, img_file

    async def _generate_mdi_image(self):
        teams = [  # Tank, Healer, DPS, DPS, DPS
            ["Jabuka", "Helmoa", "Amburator", "Ljepotanko", "Pantelinho"],
            ["Guzimir", "Ludacha", "Beargrylz", "Filecar", "Zudu"],
            ["Voortas", "Milkan", "Grubi", "Spasic", "Mageisback"],
            ["Ventilator", "Tithrál", "Zugi", "Limma", "Nedostupan"],
        ]
        team_data: list[list[Optional[ParticipantCharacter]]] = [[], [], [], []]
        for i, team in enumerate(teams):
            for player in team:
                if player == "?":
                    team_data[i].append(None)
                    continue
                character = await ParticipantCharacter.create(player)
                team_data[i].append(character)

        img = Image.open(bundled_data_path(self) / "mdi_scoreboard.png")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(str(bundled_data_path(self) / "Roboto-Bold.ttf"), 40)

        x = 194
        y = 275

        # Team 1
        team1 = team_data[0]
        await self.draw_team(draw, font, img, team1, x, y)

        # Team 2
        team2 = team_data[1]
        x = 1235
        y = 275
        await self.draw_team(draw, font, img, team2, x, y)

        # Team 3
        team3 = team_data[2]
        x = 194
        y = 953
        await self.draw_team(draw, font, img, team3, x, y)

        # Team 4
        team4 = team_data[3]
        x = 1235
        y = 953
        await self.draw_team(draw, font, img, team4, x, y)

        img_obj = io.BytesIO()
        img.save(img_obj, format="PNG")
        img_obj.seek(0)

        return discord.File(fp=img_obj, filename="scoreboard.png")

    async def draw_team(self, draw, font, img, team1, x, y):
        offset = 7
        for character in team1:
            if character is None:
                y += 113
                continue

            async with self.session.request("GET", character.thumbnail_url) as resp:
                image = await resp.content.read()
                image = Image.open(io.BytesIO(image))
                image = image.resize((97, 97))
                img.paste(image, (x - 100, y - 30))

            draw.text((x + 15, y - offset), character.name, character.get_class_color(), font=font)
            draw.text(
                (x + 375, y - offset),
                f"ilvl {str(character.item_level)}",
                (255, 0, 0) if character.item_level >= 390 else (0, 255, 0),
                font=font,
            )
            draw.text((x + 540, y - offset), str(int(character.score)), character.color, font=font)
            y += 113

    @tasks.loop(minutes=10)
    async def update_mdi_scoreboard(self):
        for guild in self.bot.guilds:
            if await self.bot.cog_disabled_in_guild(self, guild):
                continue
            await set_contextual_locales_from_guild(self.bot, guild)

            mdi_channel_id = await self.config.guild(guild).mdi_channel()
            mdi_msg_id = await self.config.guild(guild).mdi_message()
            if not (mdi_channel_id and mdi_msg_id):
                continue
            mdi_channel = guild.get_channel(mdi_channel_id)

            try:
                mdi_msg = await mdi_channel.fetch_message(mdi_msg_id)
            except discord.HTTPException:
                log.error(f"Failed to fetch MDI scoreboard message in {guild} ({guild.id}).")
                continue
            if not mdi_msg:
                continue

            embed = discord.Embed(
                title="MDI timovi",
                color=await self.bot.get_embed_color(mdi_msg),
            )
            embed.set_author(name=guild.name, icon_url=guild.icon.url)

            desc = f"Zadnji put ažurirano <t:{int(datetime.now(timezone.utc).timestamp())}:R>\n"
            desc += "Prvi dan MDI-a počinje <t:1675882800:R>\n"

            img_file = await self._generate_mdi_image()
            embed.set_image(url=f"attachment://{img_file.filename}")
            embed.set_footer(text="Ažurira se svakih 10 minuta")
            embed.description = desc

            try:
                await mdi_msg.edit(embed=embed, attachments=[img_file])
            except discord.HTTPException:
                log.error(f"Failed to edit MDI scoreboard message in {guild} ({guild.id}).")


class ParticipantCharacter:
    def __init__(self):
        self.name: str = ""
        self.thumbnail_url: str = ""
        self.item_level: int = 0
        self.score: float = 0
        self.color: str = ""
        self.player_class: str = ""

    @classmethod
    async def create(cls, name: str):
        self = ParticipantCharacter()
        self.name = name

        async with RaiderIO() as rio:
            player_data = await rio.get_character_profile(
                "eu", "ragnaros", name, ["gear", "mythic_plus_scores_by_season:current"]
            )
        self.thumbnail_url = player_data["thumbnail_url"]
        self.item_level = player_data["gear"]["item_level_equipped"]
        self.score = player_data["mythic_plus_scores_by_season"][0]["segments"]["all"]["score"]
        self.color = player_data["mythic_plus_scores_by_season"][0]["segments"]["all"]["color"]
        self.player_class = player_data["class"]

        return self

    def get_class_color(self):
        return {
            "DEATH KNIGHT": "#C41F3B",
            "DEMON HUNTER": "#A330C9",
            "DRUID": "#FF7D0A",
            "HUNTER": "#ABD473",
            "MAGE": "#69CCF0",
            "MONK": "#00FF96",
            "PALADIN": "#F58CBA",
            "PRIEST": "#FFFFFF",
            "ROGUE": "#FFF569",
            "SHAMAN": "#0070DE",
            "WARLOCK": "#9482C9",
            "WARRIOR": "#C79C6E",
            "EVOKER": "#1F594D",
        }[self.player_class.upper()]
