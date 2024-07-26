import datetime
import random
from typing import List, Tuple

import aiohttp
import aiowiki
import discord
from discord.app_commands import AppCommandContext, AppInstallationType
from redbot.core import Config, app_commands, commands
from redbot.core.commands import Context
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.views import SimpleMenu
from tabulate import tabulate

from .utils import get_timeout_timestamp

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

    slash_wikiarena = app_commands.Group(
        name="wikiarena",
        description="WikiArena commands",
        allowed_installs=AppInstallationType(guild=True, user=True),
        allowed_contexts=AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    )

    @slash_wikiarena.command(
        name="start",
        description="Start a game of WikiArena",
    )
    async def slash_wikiarena_start(self, interaction: discord.Interaction):
        """
        Starts a game of WikiArena.

        Check out the original game by Fabian Fischer! https://ludokultur.itch.io/wikiarena
        """
        # self.wiki_language = (await i18n.get_locale_from_guild(self.bot, ctx.guild)).split("-")[0]
        self.wiki_language = "en"
        await interaction.response.defer()
        await self.start_game(interaction)

    async def start_game(self, interaction: discord.Interaction):
        (
            embeds,
            blue_views,
            blue_word_count,
            red_views,
            red_word_count,
        ) = await self.game_setup(self.wiki_language)
        timeout_timestamp = get_timeout_timestamp()
        view = ButtonsView(
            config=self.config,
            wiki_language=self.wiki_language,
            blue_views=blue_views,
            red_views=red_views,
            blue_words=blue_word_count,
            red_words=red_word_count,
            author=interaction.user,
        )
        view.message = await interaction.followup.send(
            _(
                "Guess which full article has __more words__ or __more views__ in the last 60 days!\n"
                "Score: **{score}**\n"
                "Time's up {in_time}!"
            ).format(score="0", in_time=f"<t:{timeout_timestamp}:R>"),
            embeds=embeds,
            view=view,
        )

    @slash_wikiarena.command(
        name="scoreboard", description="Look at the WikiArena global scoreboard."
    )
    async def slash_wikiarena_scoreboard(self, interaction: discord.Interaction):
        """Display the WikiArena scoreboard for this guild."""
        await interaction.response.defer()
        user_data = await self.config.all_users()
        if not user_data:
            return await interaction.followup.send(_("No users have played WikiArena yet."))
        user_data = dict(sorted(user_data.items(), key=lambda x: x[1]["high_score"], reverse=True))
        scoreboard_dict = {}
        for user_id, data in user_data.items():
            user = interaction.client.get_user(user_id)
            if user is None:
                continue

            scoreboard_dict[user.name] = data["high_score"]
        if not scoreboard_dict:
            return await interaction.followup.send(_("No users have played WikiArena yet."))

        max_users_per_page = 20
        await self._send_scoreboard(interaction, max_users_per_page, scoreboard_dict)

    async def _send_scoreboard(
        self, interaction: discord.Interaction, max_users_per_page, scoreboard_dict
    ):
        tabulate_list = await self._make_tabulate_list(scoreboard_dict)
        if len(tabulate_list) > max_users_per_page:
            embeds = await self._make_scoreboard_pages(
                interaction, max_users_per_page, tabulate_list
            )
            ctx: Context = await Context.from_interaction(interaction)
            await SimpleMenu(pages=embeds, disable_after_timeout=True).start(ctx)
        else:
            embed = await self._make_scoreboard_page(interaction, scoreboard_dict, tabulate_list)
            await interaction.followup.send(embed=embed)

    @staticmethod
    async def _make_tabulate_list(scoreboard_dict):
        return [
            [f"{index + 1}.", user, score]
            for index, (user, score) in enumerate(scoreboard_dict.items())
        ]

    @staticmethod
    async def _make_scoreboard_pages(
        interaction: discord.Interaction, max_users_per_page, tabulate_friendly_list
    ) -> List[discord.Embed]:
        page_count = len(tabulate_friendly_list) // max_users_per_page
        embeds = []
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
                color=await interaction.client.get_embed_colour(interaction.channel),
            )
            embed.set_footer(
                text=_("Page {page}/{page_count} | Total players: {num_players}").format(
                    page=page + 1,
                    page_count=page_count,
                    num_players=len(tabulate_friendly_list),
                )
            )
            embeds.append(embed)
        return embeds

    @staticmethod
    async def _make_scoreboard_page(
        interaction: discord.Interaction, scoreboard_dict, tabulate_friendly_list
    ):
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
            colour=await interaction.client.get_embed_colour(interaction.channel),
        )
        embed.set_footer(
            text=_("Total players: {num_players}").format(num_players=len(scoreboard_dict))
        )
        return embed

    async def game_setup(
        self, wiki_language: str
    ) -> Tuple[List[discord.Embed], int, int, int, int]:
        wiki = aiowiki.Wiki.wikipedia(wiki_language)
        wiki_pages = await wiki.get_random_pages(num=2, namespace=0)
        embeds, page_view_counts, page_word_counts = await WikiArena.make_wiki_embeds(
            self, wiki_pages
        )
        await wiki.close()

        blue_views = page_view_counts[0]
        red_views = page_view_counts[1]
        blue_word_count = page_word_counts[0]
        red_word_count = page_word_counts[1]

        return embeds, blue_views, blue_word_count, red_views, red_word_count

    async def make_wiki_embeds(self, wiki_pages):
        embed_colours = discord.Colour.blue(), discord.Colour.red()
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
        return embeds, page_view_counts, page_word_counts

    async def get_page_views(self, page) -> int:
        today = datetime.datetime.now().strftime("%Y%m%d")
        long_time_ago = (datetime.datetime.now() - datetime.timedelta(days=60)).strftime("%Y%m%d")

        page_title = page.title.replace(" ", "_")
        request_url = (
            f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"{self.wiki_language}"
            f".wikipedia/all-access/user/"
            f"{page_title}"
            f"/daily/"
            f"{long_time_ago}"
            f"/{today}"
        )
        while True:
            async with self.session.request("GET", request_url) as resp:
                if resp.status != 200:
                    return 0

                data = await resp.json()
                return sum(day["views"] for day in data["items"])

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())


class ButtonsView(discord.ui.View):
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
        await set_contextual_locales_from_guild(interaction.client, interaction.guild)
        if not await self._owner_check(interaction):
            return
        if self.red_views < self.blue_views:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.red, row=1)
    async def red_more_views(self, interaction: discord.Interaction, button):
        await set_contextual_locales_from_guild(interaction.client, interaction.guild)
        if not await self._owner_check(interaction):
            return
        if self.red_views > self.blue_views:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.blurple)
    async def blue_more_words(self, interaction: discord.Interaction, button):
        await set_contextual_locales_from_guild(interaction.client, interaction.guild)
        if not await self._owner_check(interaction):
            return
        if self.red_words < self.blue_words:
            await self.continue_game(interaction)
        else:
            await self.end_game(interaction)

    @discord.ui.button(style=discord.ButtonStyle.red, row=1)
    async def red_more_words(self, interaction: discord.Interaction, button):
        await set_contextual_locales_from_guild(interaction.client, interaction.guild)
        if not await self._owner_check(interaction):
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
        ) = await WikiArena.game_setup(self, self.wiki_language)

        self.blue_views = blue_views
        self.red_views = red_views
        self.blue_words = blue_word_count
        self.red_words = red_word_count

        timeout_timestamp = get_timeout_timestamp()

        await interaction.response.edit_message(
            content=_(
                "Guess which full article has __more words__ or __more views__ in the last 60 days!\n"
                "Score: **{score}**\n"
                "Time's up {in_time}!"
            ).format(score=self.score, in_time=f"<t:{timeout_timestamp}:R>"),
            embeds=embeds,
            view=self,
        )

    async def end_game(self, interaction):
        self.game_status = -1
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
            blue_views=(
                f"**{self.blue_views}**" if self.blue_views > self.red_views else self.blue_views
            ),
            red_views=(
                f"**{self.red_views}**" if self.red_views > self.blue_views else self.red_views
            ),
            blue_words=(
                f"**{self.blue_words}**" if self.blue_words > self.red_words else self.blue_words
            ),
            red_words=(
                f"**{self.red_words}**" if self.red_words > self.blue_words else self.red_words
            ),
        )

        end_msg = await self.update_user_data(end_msg)
        await interaction.response.edit_message(
            content=end_msg,
            view=self,
        )

    async def update_user_data(self, end_msg):
        games_played = await self.config.user(self.author).games_played()
        await self.config.user(self.author).games_played.set(games_played + 1)

        user_high_score = await self.config.user(self.author).high_score()
        if self.score > user_high_score:
            await self.config.user(self.author).high_score.set(self.score)
            end_msg += _("\nYou've beaten your high score of **{user_high_score}**!").format(
                user_high_score=user_high_score
            )
        else:
            end_msg += _("\nYour high score is **{user_high_score}**").format(
                user_high_score=user_high_score
            )

        return end_msg

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
            blue_views=(
                f"**{self.blue_views}**" if self.blue_views > self.red_views else self.blue_views
            ),
            red_views=(
                f"**{self.red_views}**" if self.red_views > self.blue_views else self.red_views
            ),
            blue_words=(
                f"**{self.blue_words}**" if self.blue_words > self.red_words else self.blue_words
            ),
            red_words=(
                f"**{self.red_words}**" if self.red_words > self.blue_words else self.red_words
            ),
        )

        end_msg = await self.update_user_data(end_msg)
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
