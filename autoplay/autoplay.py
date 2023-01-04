import logging
from typing import Optional

import discord
from pylav.players.player import Player
from pylav.players.query.obj import Query
from pylav.type_hints.bot import DISCORD_BOT_TYPE
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

log = logging.getLogger("red.karlo-cogs.autoplay")
_ = Translator("AutoPlay", __file__)


@cog_i18n(_)
class AutoPlay(commands.Cog):
    """Automatically play music that a user is listening to on Spotify."""

    def __init__(self, bot: DISCORD_BOT_TYPE):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=87446677010550784, force_registration=True)
        default_guild = {"tracked_member": None, "autoplaying": False, "paused_track": None}
        self.config.register_guild(**default_guild)

    @commands.hybrid_command()
    @commands.guild_only()
    async def autoplay(self, ctx, member: discord.Member = None):
        """Toggle autoplay for a member."""
        if ctx.interaction:
            await ctx.defer(ephemeral=True)

        if member is None:
            await self.config.guild(ctx.guild).tracked_member.set(None)
            await ctx.send(_("No longer tracking any member."))
        else:
            await self.config.guild(ctx.guild).tracked_member.set(member.id)
            await ctx.send(
                _("I'll now play whatever {member} is listening to.").format(member=member.mention)
            )

    @commands.Cog.listener("on_presence_update")
    async def _on_presence_update(
        self, member_before: discord.Member, member_after: discord.Member
    ):
        if await self._member_checks(member_after):
            return

        player: Player = self.bot.lavalink.get_player(member_after.guild.id)
        if player is None:
            log.debug("No player found.")
            return

        current_activity = self._get_spotify_activity(member_after)
        past_activity = self._get_spotify_activity(member_before)
        if not current_activity:
            # Member is no longer listening to Spotify.
            autoplaying = await self.config.guild(member_after.guild).autoplaying()
            if autoplaying:
                await player.set_pause(True, member_after)
                await self.config.guild(member_after.guild).autoplaying.set(False)
                await self.config.guild(member_after.guild).paused_track.set(
                    past_activity.track_id
                )
            return
        log.debug(f"Presence update detected. {current_activity.track_url}")
        if past_activity and past_activity.track_id == current_activity.track_id:
            # Same track, no need to do anything.
            return
        if current_activity.track_id == await self.config.guild(member_after.guild).paused_track():
            # If the track is the same as when the activity stopped, it was probably paused,
            # so we'll resume it.
            log.debug("Resuming track.")
            await player.set_pause(False, member_after)
            await self.config.guild(member_after.guild).autoplaying.set(True)
            return

        log.debug(f"Querying {current_activity.track_url}")
        query = await Query.from_string(current_activity.track_url)
        response = await self.bot.lavalink.search_query(query=query)
        if response is None or not response.tracks:
            log.debug("No tracks found.")
            return

        log.debug(f"Query successful: {response.tracks[0]}")

        if player.paused:
            # To prevent overlapping tracks, we'll stop the player first to clear the paused track.
            await player.stop(member_after)
        if player.queue.size():
            log.debug("Queue is not empty, clearing.")
            player.queue.clear()
        log.debug(f"Playing {response.tracks[0].info.title}.")
        await player.play(
            query=query,
            track=response.tracks[0],
            requester=member_after,
        )
        await self.config.guild(member_after.guild).paused_track.set(None)
        await self.config.guild(member_after.guild).autoplaying.set(True)

    async def _member_checks(self, member: discord.Member) -> bool:
        """Check if the member is valid for autoplay."""
        return (
            member.id != tracked_member
            if (tracked_member := await self.config.guild(member.guild).tracked_member())
            else True
        )

    @staticmethod
    def _get_spotify_activity(member: discord.Member) -> Optional[discord.Spotify]:
        """Get the Spotify activity of a member."""
        return next(
            (
                activity
                for activity in member.activities
                if activity.type == discord.ActivityType.listening
                and hasattr(activity, "track_id")
                and hasattr(activity, "track_url")
            ),
            None,
        )

    @commands.Cog.listener("on_command")
    async def _on_command(self, ctx: commands.Context):
        """Stop autoplay when a player command is used."""
        log.debug(f"Command {ctx.command.name}, {ctx.command.qualified_name} used.")
        player_commands = [
            "play",
            "skip",
            "stop",
            "playlist play",
            "dc",
            "prev",
            "repeat",
            "shuffle",
        ]
        if ctx.command.name in player_commands:
            await self._stop_autoplay(ctx.guild)

    @commands.Cog.listener("on_interaction")
    async def _on_interaction(self, interaction: discord.Interaction):
        """Stop autoplay when a player interaction is used."""
        if interaction.type != discord.InteractionType.application_command:
            return
        log.debug(
            f"Interaction {interaction.type}, {interaction.command.name if interaction.command else None} used."
        )
        player_commands = [
            "play",
            "radio",
            "search",
        ]
        if interaction.command.name in player_commands:
            await self._stop_autoplay(interaction.guild)

    async def _stop_autoplay(self, guild: discord.Guild):
        await self.config.guild(guild).autoplaying.set(False)
        await self.config.guild(guild).tracked_member.set(None)

    def cog_unload(self):
        ...
