import logging
import urllib.parse
from typing import Dict, List

import aiohttp
import discord
import flag
from discord.app_commands import AppCommandContext, AppInstallationType
from redbot.core import app_commands, commands
from redbot.core.bot import Red
from redbot.core.commands import Context
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.views import SimpleMenu
from tabulate import tabulate

from w3champions.league import W3ChampionsLeague
from w3champions.mode import ModeType, W3ChampionsMode
from w3champions.player import ModeStats, OngoingMatch, RaceStats, W3ChampionsPlayer
from w3champions.profile_picture_race import W3ChampionsProfilePictureRace
from w3champions.race import Race
from w3champions.ranking_player import W3ChampionsRankingPlayer
from w3champions.season import W3ChampionsSeason

_ = Translator("W3Champions", __file__)
log = logging.getLogger("red.karlo-cogs.w3champions")


@cog_i18n(_)
class W3Champions(commands.Cog):
    def __init__(self, bot):
        self.bot: Red = bot
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Red-DiscordBot/karlo-cogs/W3ChampionsCog"}
        )
        self.w3c_modes: List[W3ChampionsMode] = []
        self.w3c_seasons: List[W3ChampionsSeason] = []
        self.current_season: int = 0
        self.w3c_leagues: Dict[int, Dict[int, List[W3ChampionsLeague]]] = {}

    async def cog_load(self) -> None:
        self.w3c_modes = await self.fetch_w3c_modes()
        self.w3c_seasons = await self.fetch_w3c_seasons()
        self.current_season = self.w3c_seasons[0].id

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
            season = W3ChampionsSeason(id=entry["id"])
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
        await interaction.response.defer()
        rankings = await self.fetch_ladder_players(
            interaction, season, mode.split(":")[1], league.split(":")[1]
        )

        rows = [player.to_row() for player in rankings]
        max_per_page = 20
        page_count = (len(rows) + max_per_page - 1) // max_per_page
        pages = []
        for page in range(page_count):
            from_here = page * max_per_page
            to_there = from_here + max_per_page
            table = tabulate(
                rows[from_here:to_there],
                headers=headers,
                tablefmt="plain",
                disable_numparse=True,
            )
            content = f"Season {season} - {mode.split(':')[0]} - {league.split(':')[0]}\n{box(table, 'md')}"
            pages.append(content)
        ctx: Context = await Context.from_interaction(interaction)
        await (SimpleMenu(pages=pages, disable_after_timeout=True)).start(ctx)
        # await interaction.followup.send(content)

    @slash_w3champions.command(name="profile")
    @app_commands.describe(player="The full battletag of the user you want to look up")
    async def slash_w3champions_profile(self, interaction: discord.Interaction, player: str):
        if len(player.split("#")) != 2:
            await interaction.response.send_message(
                "Please input the full Battletag of the user you want to look up. (Name#12345)",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        try:
            profile: W3ChampionsPlayer = await self.fetch_player_profile(player)
        except Exception as e:
            await interaction.followup.send(f"{player} not found.")
            log.warning(f"{player} not found.", exc_info=e)
            return

        embed: discord.Embed = self.make_profile_embed(
            profile,
            await interaction.client.get_embed_colour(interaction.channel),  # type: ignore
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label=_("Profile"),
                style=discord.ButtonStyle.link,
                url=profile.get_player_url(),
            )
        )
        await interaction.followup.send(embed=embed, view=view)

    async def fetch_player_profile(self, player: str) -> W3ChampionsPlayer:
        personal_settings: Dict = await self.fetch_personal_settings(player)
        total_wins = sum([int(race["wins"]) for race in personal_settings.get("winLosses", [])])
        total_games = sum([int(race["games"]) for race in personal_settings.get("winLosses", [])])
        profile_picture_url: str = self.get_profile_picture_url(
            personal_settings["profilePicture"]["race"],
            personal_settings["profilePicture"]["pictureId"],
            personal_settings["profilePicture"]["isClassic"],
        )

        mode_stats: List[ModeStats] = await self.fetch_mode_stats(player)
        race_stats: List[RaceStats] = await self.fetch_race_stats(player)
        ongoing: OngoingMatch | None = await self.fetch_ongoing_match(player)

        return W3ChampionsPlayer(
            name=player,
            location=personal_settings["location"],
            profile_picture_url=profile_picture_url,
            total_games=total_games,
            total_wins=total_wins,
            stats_by_mode=mode_stats,
            stats_by_race=race_stats,
            ongoing_match=ongoing,
        )

    async def fetch_ongoing_match(self, player: str) -> OngoingMatch | None:
        request_url = urllib.parse.quote(
            f"https://website-backend.w3champions.com/api/matches/ongoing/{player}", safe=":/"
        )
        data: Dict = {}
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
        ongoing = OngoingMatch(map_name=data["mapName"])
        return ongoing

    async def fetch_personal_settings(self, player: str) -> Dict:
        request_url = urllib.parse.quote(
            f"https://website-backend.w3champions.com/api/personal-settings/{player}", safe=":/"
        )
        data: Dict = {}
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                raise ValueError
            data = await resp.json()
        return data

    def get_profile_picture_url(self, race: int, picture_id: int, classic: bool) -> str:
        return (
            (
                "https://w3champions.wc3.tools/prod/integration/icons/raceAvatars/"
                f"{'classic/' if classic else ''}{W3ChampionsProfilePictureRace(race).name}_{picture_id}.jpg?v=2"
            )
            if race != 32
            else (
                "https://w3champions.wc3.tools/prod/integration/icons/specialAvatars/"
                f"{W3ChampionsProfilePictureRace(race).name}_{picture_id}.jpg?v=2"
            )
        )

    async def fetch_mode_stats(self, player: str) -> List[ModeStats]:
        request_url = urllib.parse.quote(
            f"https://website-backend.w3champions.com/api/players/{player}/game-mode-stats",
            safe=":/",
        )
        params = {"gateWay": self.current_season, "season": self.current_season}
        data: List[Dict] = []
        async with self.session.request("GET", request_url, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        mode_stats = []
        for mode in data:
            gamemode = self.get_gamemode_from_id(mode["gameMode"])
            if not gamemode:
                continue
            mode_stats.append(
                ModeStats(
                    gamemode=gamemode,
                    race=Race(mode["race"]) if mode["race"] else None,
                    mmr=mode["mmr"],
                    quantile=mode["quantile"],
                    wins=mode["wins"],
                    losses=mode["losses"],
                    games=mode["games"],
                    winrate=mode["winrate"],
                )
            )
        return mode_stats

    def get_gamemode_from_id(self, id: int) -> W3ChampionsMode | None:
        for mode in self.w3c_modes:
            if mode.id == id:
                return mode
        return None

    async def fetch_race_stats(self, player: str) -> List[RaceStats]:
        request_url = urllib.parse.quote(
            f"https://website-backend.w3champions.com/api/players/{player}/race-stats",
            safe=":/",
        )
        params = {"gateWay": self.current_season, "season": self.current_season}
        data: List[Dict] = []
        async with self.session.request("GET", request_url, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        return [
            RaceStats(
                race=Race(race["race"]),
                wins=race["wins"],
                losses=race["losses"],
                games=race["games"],
                winrate=race["winrate"],
            )
            for race in data
        ]

    def make_profile_embed(
        self, profile: W3ChampionsPlayer, colour: discord.Color
    ) -> discord.Embed:
        description = f"Games:{profile.total_games}\nWins: {profile.total_wins}"
        embed = discord.Embed(
            color=colour,
            title=f"{profile.name} {flag.flag(profile.location)}",
            description=description,
            url=profile.get_player_url(),
        )

        if profile.ongoing_match:
            embed.add_field(
                name=_("Playing"),
                value=_("Currently playing on {mapName}").format(
                    mapName=profile.ongoing_match.map_name
                ),
            )

        if profile.stats_by_race:
            headers = [_("# Race"), _("Win"), _("Loss"), _("WR%")]
            rows = [race.to_row() for race in profile.stats_by_race]
            table = tabulate(rows, headers=headers, tablefmt="plain", disable_numparse=True)
            embed.add_field(name=_("Stats by race"), value=box(table, "md"), inline=False)

        if profile.stats_by_mode:
            headers = [_("# Mode"), _("Win"), _("Loss"), _("WR%"), _("MMR")]
            rows = [mode.to_row() for mode in profile.stats_by_mode]
            table = tabulate(rows, headers=headers, tablefmt="plain", disable_numparse=True)
            embed.add_field(name=_("Stats by mode"), value=box(table, "md"), inline=False)

        embed.set_thumbnail(url=profile.profile_picture_url)
        return embed

    async def fetch_ladder_players(
        self, interaction: discord.Interaction, season: int, mode: str, league: str
    ) -> List[W3ChampionsRankingPlayer]:
        request_url = f"https://website-backend.w3champions.com/api/ladder/{league}"
        params = {
            "gateWay": self.current_season,  # idk what this is. current season? guess we'll find out later
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
                        W3ChampionsLeague(
                            division=league["division"], id=league["id"], name=league["name"]
                        )
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
