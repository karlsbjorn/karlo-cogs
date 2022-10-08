import datetime
import random
from typing import List, Tuple

import aiohttp
import aiowiki
import discord
from redbot.core import Config, commands, i18n
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from tabulate import tabulate

_ = Translator("WikiArena", __file__)


@cog_i18n(_)
class WikiArena(commands.Cog):
    """WikiArena

    A Wikipedia game heavily inspired by **WikiArena** by Fabian Fischer.

    Check out the original game! https://ludokultur.itch.io/wikiarena
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=87446677010550784)
        self.wiki_language = "en"
        self.session = aiohttp.ClientSession()
        default_user = {
            "high_score": 0,
            "games_played": 0,
        }
        self.config.register_user(**default_user)

    @commands.command()
    async def wikiarena(self, ctx):
        """
        Starts a game of WikiArena.

        Check out the original game by Fabian Fischer! https://ludokultur.itch.io/wikiarena
        """
        self.wiki_language = (await i18n.get_locale_from_guild(self.bot, ctx.guild)).split("-")[0]
        async with ctx.typing():
            (
                embeds,
                blue_views,
                blue_word_count,
                red_views,
                red_word_count,
            ) = await self.game_setup(self.wiki_language)

            view = Buttons(
                config=self.config,
                wiki_language=self.wiki_language,
                blue_views=blue_views,
                red_views=red_views,
                blue_words=blue_word_count,
                red_words=red_word_count,
                author=ctx.author,
            )
            view.message = await ctx.send(
                _(
                    "Guess which full article has __more words__ or __more views__ in the last 60 days!\n"
                    "Score: **{score}**"
                ).format(score="0"),
                embeds=embeds,
                view=view,
            )

    @commands.command(aliases=["wikiarenascoreboard"])
    async def wascoreboard(self, ctx):
        """Display the WikiArena scoreboard for this guild."""
        max_users_per_page = 1
        user_data = await self.config.all_users()
        if not user_data:
            return await ctx.send(_("No users have played WikiArena yet."))
        user_data = dict(sorted(user_data.items(), key=lambda x: x[1]["high_score"], reverse=True))
        scoreboard_dict = {}
        for user_id, data in user_data.items():
            member = ctx.guild.get_member(user_id)
            if member is None:
                continue

            scoreboard_dict[member.display_name] = data["high_score"]
        if not scoreboard_dict:
            return await ctx.send(_("No users in this guild have played WikiArena yet."))

        tabulate_friendly_list = []
        for index, (member, score) in enumerate(scoreboard_dict.items()):
            tabulate_friendly_list.append([f"{index + 1}.", member, score])

        embeds = []
        if len(tabulate_friendly_list) > max_users_per_page:
            page_count = len(tabulate_friendly_list) // max_users_per_page
            for page in range(page_count):
                from_here = page
                to_there = (page + 1) * max_users_per_page
                scoreboard = box(
                    tabulate(
                        tabulate_friendly_list[from_here:to_there],
                        headers=["#", _("Name"), _("Score")],
                        tablefmt="plain",
                        disable_numparse=True,
                    ),
                    lang="md",
                )
                embed = discord.Embed(
                    title=_("WikiArena Scoreboard"),
                    description=scoreboard,
                    color=await ctx.embed_color(),
                )
                embed.set_footer(
                    text=_("Page {page}/{page_count}").format(page=page, page_count=page_count)
                )
                embeds.append(embed)

        scoreboard = box(
            tabulate(
                tabulate_friendly_list,
                headers=["#", _("Name"), _("Score")],
                tablefmt="plain",
                disable_numparse=True,
            ),
            lang="md",
        )

        embed = discord.Embed(
            title=_("WikiArena Scoreboard"),
            description=scoreboard,
            colour=await ctx.embed_colour(),
        )
        embed.set_footer(
            text=_("Total players: {num_players}").format(num_players=len(scoreboard_dict))
        )

        if embeds:
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send(embed=embed)

    async def game_setup(
        self, wiki_language: str
    ) -> Tuple[List[discord.Embed], int, int, int, int]:
        wiki = aiowiki.Wiki.wikipedia(wiki_language)
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
            try:
                page_media = await page.media()
            except KeyError:
                page_media = None
            if page_media:
                embed.set_thumbnail(url=page_media[0])

            max_word_count = random.randint(30, 60)  # TODO: Make this a configurable value
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
        today = datetime.datetime.now().strftime("%Y%m%d")
        long_time_ago = (datetime.datetime.now() - datetime.timedelta(days=60)).strftime("%Y%m%d")

        page_title = page.title.replace(" ", "_")
        request_url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{self.wiki_language}.wikipedia/all-access/user/{page_title}/daily/{long_time_ago}/{today}"
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                raise ValueError(f"That article does not exist. {request_url}")

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
        self,
        config,
        wiki_language,
        blue_views,
        red_views,
        blue_words,
        red_words,
        author,
        timeout=180,
    ):
        super().__init__(timeout=timeout)
        self.config: Config = config
        self.message = None
        self.author = author
        self.score = 0
        self.game_status = 0
        self.wiki_language = wiki_language
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

    @discord.ui.button(style=discord.ButtonStyle.blurple)
    async def blue_more_views(self, interaction: discord.Interaction, button):
        await self._owner_check(interaction)
        if self.red_views < self.blue_views:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.red, row=1)
    async def red_more_views(self, interaction: discord.Interaction, button):
        await self._owner_check(interaction)
        if self.red_views > self.blue_views:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.blurple)
    async def blue_more_words(self, interaction: discord.Interaction, button):
        await self._owner_check(interaction)
        if self.red_words < self.blue_words:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.red, row=1)
    async def red_more_words(self, interaction: discord.Interaction, button):
        await self._owner_check(interaction)
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
        ) = await WikiArena.game_setup(self, self.wiki_language)
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
        self.game_status = -1
        embeds = []
        for child in self.children:
            child.disabled = True
        end_msg = _(
            "Wrong! Better luck next time!\n"
            "🔵 Views: {blue_views}\n"
            "🔵 Words: {blue_words}\n"
            "🔴 Views: {red_views}\n"
            "🔴 Words: {red_words}\n\n"
            "Your final score was: **{score}**"
        ).format(
            score=self.score,
            blue_views=f"**{self.blue_views}**"
            if self.blue_views > self.red_views
            else self.blue_views,
            red_views=f"**{self.red_views}**"
            if self.red_views > self.blue_views
            else self.red_views,
            blue_words=f"**{self.blue_words}**"
            if self.blue_words > self.red_words
            else self.blue_words,
            red_words=f"**{self.red_words}**"
            if self.red_words > self.blue_words
            else self.red_words,
        )

        games_played = await self.config.user(self.author).games_played()
        await self.config.user(self.author).games_played.set(games_played + 1)

        user_high_score = await self.config.user(self.author).high_score()
        if self.score > user_high_score:
            await self.config.user(self.author).high_score.set(self.score)
            end_msg += _("\nYou've beaten your high score of **{user_high_score}**!").format(
                user_high_score=user_high_score
            )
            end_msg += _("\nYour new high score is **{score}**").format(score=self.score)
        else:
            end_msg += _("\nYour high score is **{user_high_score}**").format(
                user_high_score=user_high_score
            )
        await interaction.response.edit_message(
            content=end_msg,
            embeds=embeds,
            view=self,
        )

    async def on_timeout(self):
        if self.game_status == -1:
            return
        embeds = []
        for item in self.children:
            item.disabled = True
        end_msg = _(
            "Time's up! Be faster next time!\n"
            "🔵 Views: {blue_views}\n"
            "🔵 Words: {blue_words}\n"
            "🔴 Views: {red_views}\n"
            "🔴 Words: {red_words}\n\n"
            "Your final score was: **{score}**"
        ).format(
            score=self.score,
            blue_views=f"**{self.blue_views}**"
            if self.blue_views > self.red_views
            else self.blue_views,
            red_views=f"**{self.red_views}**"
            if self.red_views > self.blue_views
            else self.red_views,
            blue_words=f"**{self.blue_words}**"
            if self.blue_words > self.red_words
            else self.blue_words,
            red_words=f"**{self.red_words}**"
            if self.red_words > self.blue_words
            else self.red_words,
        )

        games_played = await self.config.member(self.author).games_played()
        await self.config.member(self.author).games_played.set(games_played + 1)

        user_high_score = await self.config.user(self.author).high_score()
        if self.score > user_high_score:
            await self.config.user(self.author).high_score.set(self.score)
            end_msg += _("\nYou've beaten your high score of **{user_high_score}**!").format(
                user_high_score=user_high_score
            )
        else:
            end_msg += _("\nYour high score is **{user_high_score}**.").format(
                user_high_score=user_high_score
            )
        await self.message.edit(
            content=end_msg,
            embeds=embeds,
            view=self,
        )

    async def _owner_check(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction is from the player."""
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(
                _("This isn't your game of WikiArena."), ephemeral=True
            )
            return False
        return True

    async def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
