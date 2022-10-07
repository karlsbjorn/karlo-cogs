import datetime
import random
from typing import List, Tuple

import aiohttp
import aiowiki
import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("WikiArena", __file__)


@cog_i18n(_)
class WikiArena(commands.Cog):
    """WikiArena

    A Wikipedia game heavily inspired by **WikiArena** by Fabian Fischer.

    Check out the original game! https://ludokultur.itch.io/wikiarena
    """

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        # TODO: Save a player's score

    @commands.command()
    async def wikiarena(self, ctx):
        """
        Starts a game of WikiArena.

        Check out the original game by Fabian Fischer! https://ludokultur.itch.io/wikiarena
        """
        score = 0
        async with ctx.typing():
            (
                embeds,
                blue_views,
                blue_word_count,
                red_views,
                red_word_count,
            ) = await self.game_setup()

            await ctx.send(
                _(
                    "Guess which full article has __more words__ or __more views__ in the last 60 days!\n"
                    "Score: **{score}**"
                ).format(score=score),
                embeds=embeds,
                view=Buttons(
                    score=score,
                    blue_views=blue_views,
                    red_views=red_views,
                    blue_words=blue_word_count,
                    red_words=red_word_count,
                    author=ctx.author,
                ),
            )

    async def game_setup(self) -> Tuple[List[discord.Embed], int, int, int, int]:
        wiki = aiowiki.Wiki.wikipedia(
            "en"
        )  # TODO: Use wikipedia language of bot's locale
        wiki_pages = await wiki.get_random_pages(num=2, namespace=0)
        embed_colours = discord.Colour.blurple(), discord.Colour.red()
        page_view_counts = []
        page_word_counts = []
        embeds = []
        for page, colour in zip(wiki_pages, embed_colours):
            embed = discord.Embed(colour=colour)

            page_title = page.title
            page_text: str = await page.summary()
            page_views = await WikiArena.get_page_views(self, page)
            page_media = await page.media()
            if page_media:
                embed.set_thumbnail(url=page_media[0])

            max_word_count = random.randint(
                30, 60  # TODO: Make this a configurable value
            )
            page_word_count = len(page_text.split())
            embed_text = " ".join(page_text.split()[:max_word_count])
            if max_word_count < page_word_count:
                embed_text += "..."

            embed.add_field(name=page_title, value=embed_text)

            page_view_counts.append(page_views)
            page_word_counts.append(page_word_count)
            embeds.append(embed)
        await wiki.close()
        blue_views = page_view_counts[0]
        red_views = page_view_counts[1]
        blue_word_count = page_word_counts[0]
        red_word_count = page_word_counts[1]
        return embeds, blue_views, blue_word_count, red_views, red_word_count

    async def get_page_views(self, page) -> int:
        today = datetime.datetime.today().strftime("%Y%m%d")
        long_time_ago = (
            datetime.datetime.today() - datetime.timedelta(days=60)
        ).strftime("%Y%m%d")

        page_title = page.title.replace(" ", "_")
        request_url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{page_title}/daily/{long_time_ago}/{today}"
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                raise ValueError("That article does not exist")
            data = await resp.json()

            page_views = 0
            for day in data["items"]:
                page_views += day["views"]

            return page_views

    # @commands.command()
    # async def waleaderboard(self, ctx):
    #     """
    #     Displays the top 10 players of WikiArena.
    #     """
    #     raise NotImplementedError

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())


class Buttons(discord.ui.View):
    def __init__(
        self, score, blue_views, red_views, blue_words, red_words, author, timeout=180
    ):
        super().__init__(timeout=timeout)
        self.author = author
        self.score = score
        self.blue_views = blue_views
        self.red_views = red_views
        self.blue_words = blue_words
        self.red_words = red_words
        # Thanks Flame!
        self.blue_more_views.label = _("More views")
        self.red_more_views.label = _("More views")
        self.blue_more_words.label = _("More words")
        self.red_more_words.label = _("More words")
        self.session = aiohttp.ClientSession()

    async def on_timeout(self):
        embeds = []
        for item in self.children:
            item.disabled = True
        await self.message.edit(
            content=_(
                "Time's up! Be faster next time!\n"
                "🔵 Views: {blue_views}\n"
                "🔴 Views: {red_views}\n"
                "🔵 Words: {blue_words}\n"
                "🔴 Words: {red_words}\n\n"
                "Your final score was: **{score}**"
            ).format(
                score=self.score,
                blue_views=self.blue_views
                if not self.blue_views > self.red_views
                else f"**{self.blue_views}**",
                red_views=self.red_views
                if not self.red_views > self.blue_views
                else f"**{self.red_views}**",
                blue_words=self.blue_words
                if not self.blue_words > self.red_words
                else f"**{self.blue_words}**",
                red_words=self.red_words
                if not self.red_words > self.blue_words
                else f"**{self.red_words}**",
            ),
            embeds=embeds,
            view=self,
        )

    @discord.ui.button(style=discord.ButtonStyle.blurple)
    async def blue_more_views(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(
                _("This isn't your game of WikiArena."), ephemeral=True
            )
            return
        if self.red_views < self.blue_views:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.red, row=1)
    async def red_more_views(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(
                _("This isn't your game of WikiArena."), ephemeral=True
            )
            return
        if self.red_views > self.blue_views:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.blurple)
    async def blue_more_words(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(
                _("This isn't your game of WikiArena."), ephemeral=True
            )
            return
        if self.red_words < self.blue_words:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.red, row=1)
    async def red_more_words(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(
                _("This isn't your game of WikiArena."), ephemeral=True
            )
            return
        if self.red_words > self.blue_words:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    async def continue_game(self, interaction):
        self.score += 1
        (
            embeds,
            blue_views,
            blue_word_count,
            red_views,
            red_word_count,
        ) = await WikiArena.game_setup(self)
        self.blue_views = blue_views
        self.red_views = red_views
        self.blue_words = blue_word_count
        self.red_words = red_word_count
        await interaction.response.edit_message(
            content=_(
                "Guess which full article has __more words__ or __more views__ in the last 60 days!\n"
                "Score: **{score}**"
            ).format(score=self.score),
            embeds=embeds,
            view=self,
        )

    async def end_game(self, interaction):
        embeds = []
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=_(
                "Wrong! Better luck next time!\n"
                "🔵 Views: {blue_views}\n"
                "🔴 Views: {red_views}\n"
                "🔵 Words: {blue_words}\n"
                "🔴 Words: {red_words}\n\n"
                "Your final score was: **{score}**"
            ).format(
                score=self.score,
                blue_views=self.blue_views
                if not self.blue_views > self.red_views
                else f"**{self.blue_views}**",
                red_views=self.red_views
                if not self.red_views > self.blue_views
                else f"**{self.red_views}**",
                blue_words=self.blue_words
                if not self.blue_words > self.red_words
                else f"**{self.blue_words}**",
                red_words=self.red_words
                if not self.red_words > self.blue_words
                else f"**{self.red_words}**",
            ),
            embeds=embeds,
            view=self,
        )

    async def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
