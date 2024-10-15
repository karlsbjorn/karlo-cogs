import logging
from typing import Dict, List

import aiohttp
import discord
from discord.app_commands import AppCommandContext, AppInstallationType
from redbot.core import app_commands, commands
from redbot.core.bot import Red
from redbot.core.commands import Context
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.views import SimpleMenu
from tabulate import tabulate

from w3champions.w3champions_league import W3ChampionsLeague
from w3champions.w3champions_mode import ModeType, W3ChampionsMode
from w3champions.w3champions_ranking_player import W3ChampionsRankingPlayer
from w3champions.w3champions_season import W3ChampionsSeason

_ = Translator("W3Champions", __file__)
log = logging.getLogger("red.karlo-cogs.w3champions")


@cog_i18n(_)
class W3Champions(commands.Cog):
    def __init__(self, bot):
        self.bot: Red = bot
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Red-DiscordBot/W3ChampionsCog"}
        )
        self.w3c_modes: List[W3ChampionsMode] = None
        self.w3c_seasons: List[W3ChampionsSeason] = None
        self.w3c_leagues: Dict[int, Dict[int, List[W3ChampionsLeague]]] = {}

    async def cog_load(self) -> None:
        self.w3c_modes = await self.fetch_w3c_modes()
        self.w3c_seasons = await self.fetch_w3c_seasons()

    async def fetch_w3c_modes(self) -> List[W3ChampionsMode]:
        request_url = "https://website-backend.w3champions.com/api/ladder/active-modes"
        data: List[Dict] = []
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                log.error(f"Error fetching W3C gamemodes: {resp.status}")
                return []
            data = await resp.json()

        mode_list = []
        for entry in data:
            try:
                mode_type = ModeType[entry["type"]]
            except KeyError:
                log.error(f"Invalid mode type found: {entry['type']}")
                continue
            mode = W3ChampionsMode(id=entry["id"], name=entry["name"], type=mode_type)
            mode_list.append(mode)
        return mode_list

    async def fetch_w3c_seasons(self) -> List[W3ChampionsSeason]:
        request_url = "https://website-backend.w3champions.com/api/ladder/seasons"
        data: List[Dict] = []
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                log.error(f"Error fetching W3C seasons: {resp.status}")
                return []
            data = await resp.json()

        season_list = []
        for entry in data:
            season = W3ChampionsSeason(entry["id"])
            season_list.append(season)
        return season_list

    slash_w3champions = app_commands.Group(
        name="w3champions",
        description=_("W3Champions commands"),
        allowed_installs=AppInstallationType(guild=True, user=True),
        allowed_contexts=AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    )

    @slash_w3champions.command(name="rankings")
    @app_commands.describe(
        season="Which season", mode="Which mode to look up", league="What league"
    )
    async def slash_w3champions_rankings(
        self, interaction: discord.Interaction, season: int, mode: str, league: str
    ) -> None:
        headers = [
            _("#"),
            _("Player"),
            _("Wins"),
            _("Losses"),
            _("Total"),
            _("Winrate"),
            _("MMR"),
        ]
        # await interaction.response.defer()
        rankings = await self.fetch_ladder_players(
            interaction, season, mode.split(":")[1], league.split(":")[1]
        )

        rows = [player.to_row() for player in rankings]
        max_per_page = 20
        page_count = (len(rows) + max_per_page - 1) // max_per_page
        pages = []
        for page in range(page_count):
            from_here = page * max_per_page  # 0  20
            to_there = from_here + max_per_page  # 20  40
            table = tabulate(
                rows[from_here:to_there],
                headers=headers,
                tablefmt="plain",
                disable_numparse=True,
            )
            content = f"Season {season} - {mode.split(':')[0]} - {league.split(':')[0]}\n{box(table, 'md')}"
            pages.append(content)
        ctx: Context = await Context.from_interaction(interaction)
        await SimpleMenu(pages=pages, disable_after_timeout=True).start(ctx)
        # await interaction.followup.send(content)

    async def fetch_ladder_players(
        self, interaction: discord.Interaction, season: int, mode: str, league: str
    ) -> List[W3ChampionsRankingPlayer]:
        request_url = f"https://website-backend.w3champions.com/api/ladder/{league}"
        params = {
            "gateWay": 20,  # idk what this is. current season? guess we'll find out later
            "gameMode": mode,
            "season": season,
        }
        data: List[Dict] = []
        async with self.session.request("GET", request_url, params=params) as resp:
            if resp.status != 200:
                log.error(f"Error fetching W3C rankings: {resp.status}")
                await interaction.followup.send("Error fetching W3C rankings.")
            data = await resp.json()

        rankings: List[W3ChampionsRankingPlayer] = []
        for ranking in data:
            player = W3ChampionsRankingPlayer(
                rank_number=ranking["rankNumber"],
                name=ranking["player"]["name"],
                location=ranking["playersInfo"][0]["location"],
                wins=ranking["player"]["wins"],
                losses=ranking["player"]["losses"],
                total_games=ranking["player"]["games"],
                winrate=ranking["player"]["winrate"],
                mmr=ranking["player"]["mmr"],
            )
            rankings.append(player)
        return rankings

    @slash_w3champions_rankings.autocomplete("season")
    async def slash_w3champions_rankings_season_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[int]]:
        seasons = [
            app_commands.Choice(name=f"Season {n.id}", value=n.id) for n in self.w3c_seasons
        ]
        return seasons[-25:]

    @slash_w3champions_rankings.autocomplete("mode")
    async def slash_w3champions_rankings_mode_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        modes = [
            app_commands.Choice(name=f"{mode.name}", value=f"{mode.name}:{mode.id}")
            for mode in self.w3c_modes
            if current.lower() in mode.name.lower()
        ]
        return modes[:25]

    @slash_w3champions_rankings.autocomplete("league")
    async def slash_w3champions_rankings_league_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        wanted_season: int = interaction.namespace.season
        wanted_mode: int = int((interaction.namespace.mode).split(":")[1])
        if wanted_season is None or wanted_mode is None:
            return []

        if not self.w3c_leagues.get(wanted_season) or not self.w3c_leagues[wanted_season].get(
            wanted_mode
        ):
            # Not cached
            request_url = "https://website-backend.w3champions.com/api/ladder/league-constellation"
            params = {"season": wanted_season}
            data: List[Dict] = []
            async with self.session.request("GET", request_url, params=params) as resp:
                if resp.status != 200:
                    log.error(f"Error fetching W3C gamemodes: {resp.status}")
                    return []
                data = await resp.json()

            leagues: List[W3ChampionsLeague] = []
            for mode in data:
                if wanted_mode != mode["gameMode"]:
                    continue
                for league in mode.get("leagues", []):
                    leagues.append(
                        W3ChampionsLeague(league["division"], league["id"], league["name"])
                    )
            if not self.w3c_leagues.get(wanted_season):
                self.w3c_leagues[wanted_season] = {}
            self.w3c_leagues[wanted_season][wanted_mode] = leagues
        else:
            # Cached
            leagues = self.w3c_leagues[wanted_season][wanted_mode]

        return [
            app_commands.Choice(
                name=f"{league.name} {league.division if league.division > 0 else ''}",
                value=f"{league.name} {league.division if league.division > 0 else ''}:{league.id}",
            )
            for league in leagues
            if current.lower() in league.name.lower()
        ][:25]

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
