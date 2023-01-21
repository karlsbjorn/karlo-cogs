from typing import Optional

import discord
from discord import AppCommandType
from pylav.events.player import PlayerDisconnectedEvent
from pylav.logging import getLogger
from pylav.players.player import Player
from pylav.players.query.obj import Query
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_INTERACTION_TYPE
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n

log = getLogger("red.karlo-cogs.autoplay")
_ = Translator("AutoPlay", __file__)


@cog_i18n(_)
class AutoPlay(commands.Cog):
    """Automatically play music that a guild member is listening to on Spotify."""

    def __init__(self, bot: DISCORD_BOT_TYPE):
        self.bot: DISCORD_BOT_TYPE = bot
        self.config = Config.get_conf(self, identifier=87446677010550784, force_registration=True)
        default_guild = {"tracked_member": None, "autoplaying": False, "paused_track": None}
        self.config.register_guild(**default_guild)
        self.context_user_autoplay = discord.app_commands.ContextMenu(
            name=_("Start AutoPlay"),
            callback=self._context_user_autoplay,
            type=AppCommandType.user,
        )
        self.bot.tree.add_command(self.context_user_autoplay)

    @commands.hybrid_command()
    @commands.guild_only()
    async def autoplay(self, ctx, member: discord.Member = None):
        """Toggle autoplay for a member.

        This will cause the bot to automatically play music that the member is listening to on Spotify.
        To stop it, use `[p]autoplay` without a member, or use a player command like `[p]stop` or `[p]play`.
        """
        if ctx.interaction:
            await ctx.defer(ephemeral=True)

        if member is None:
            await self.config.guild(ctx.guild).tracked_member.set(None)
            await ctx.send(
                embed=await self.pylav.construct_embed(
                    description=_("I'll no longer autoplay."), messageable=ctx
                )
            )
            return
        else:
            await self.config.guild(ctx.guild).tracked_member.set(member.id)
            await ctx.send(
                embed=await self.pylav.construct_embed(
                    description=_("I'll now play whatever {member} is listening to.").format(
                        member=member.mention
                    ),
                    messageable=ctx,
                )
            )

        await self._prepare_autoplay(ctx.guild, ctx.author)

    async def _context_user_autoplay(
        self, interaction: DISCORD_INTERACTION_TYPE, member: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    description=_("This can only be used in a guild."), messageable=interaction
                )
            )
            return

        await self.config.guild(interaction.guild).tracked_member.set(member.id)
        await interaction.followup.send(
            embed=await self.pylav.construct_embed(
                description=_(
                    "I'll now play whatever {member} is listening to.\n"
                    "To stop autoplay, use a player command like `stop`"
                ).format(member=member.mention),
                messageable=interaction,
            )
        )

        await self._prepare_autoplay(interaction.guild, interaction.user)

    async def _prepare_autoplay(self, guild, author):
        player: Player = self.bot.pylav.get_player(guild.id)

        if not player and author.voice:
            await self.bot.pylav.connect_player(author, author.voice.channel)
        elif player and player.channel.id != author.voice.channel.id:
            await player.move_to(author, author.voice.channel)

        if player.is_playing or player.paused:
            await player.stop(author)
        if player.queue.size:
            player.queue.clear()

    @commands.Cog.listener()
    async def on_presence_update(
        self, member_before: discord.Member, member_after: discord.Member
    ):
        if await self._member_checks(member_after):
            return

        player: Player = self.bot.lavalink.get_player(member_after.guild.id)
        if player is None:
            log.verbose("No player found.")
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
        log.verbose(f"Presence update detected. {current_activity.track_url}")
        if past_activity and past_activity.track_id == current_activity.track_id:
            # Same track, no need to do anything.
            return
        if current_activity.track_id == await self.config.guild(member_after.guild).paused_track():
            # If the track is the same as when the activity stopped, it was probably paused,
            # so we'll resume it.
            log.verbose("Resuming track.")
            await player.set_pause(False, member_after)
            await self.config.guild(member_after.guild).autoplaying.set(True)
            return

        log.verbose(f"Querying {current_activity.track_url}")
        query = await Query.from_string(current_activity.track_url)
        response = await self.bot.lavalink.search_query(query=query)
        if response is None or not response.tracks:
            log.verbose(f"No tracks found. Response: {response}")
            return

        log.verbose(f"Query successful: {response.tracks[0]}")

        if player.paused:
            # To prevent overlapping tracks, we'll stop the player first to clear the paused track.
            await player.stop(member_after)
        if player.queue.size():
            log.verbose("Queue is not empty, clearing.")
            player.queue.clear()
        log.verbose(f"Playing {response.tracks[0].info.title}.")
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

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        """Stop autoplay when a player command is used."""
        log.verbose(f"Command {ctx.command.name}, {ctx.command.qualified_name} used.")
        player_commands = [
            "play",
            "skip",
            "stop",
            "playlist play",
            "dc",
            "prev",
            "repeat",
            "shuffle",
            "pause",
            "resume",
        ]
        if ctx.command.name in player_commands:
            await self._stop_autoplay(ctx.guild)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Stop autoplay when a player interaction is used."""
        if interaction.type != discord.InteractionType.application_command:
            return
        log.verbose(
            f"Interaction {interaction.type}, "
            f"{interaction.command.name if interaction.command else None} used."
        )
        player_commands = [
            "play",
            "radio",
            "search",
        ]
        if interaction.command.name in player_commands:
            await self._stop_autoplay(interaction.guild)

    @commands.Cog.listener()
    async def on_pylav_player_disconnected_event(self, event: PlayerDisconnectedEvent):
        """Stop autoplay when the player is disconnected."""
        guild = event.player.channel.guild
        log.verbose(f"Player in {guild} disconnected.")
        await self.pylav.player_state_db_manager.delete_player(guild.id)
        await self._stop_autoplay(guild)

    async def _stop_autoplay(self, guild: discord.Guild):
        if not await self.config.guild(guild).autoplaying():
            return
        log.verbose("Stopping autoplay.")
        await self.config.guild(guild).autoplaying.set(False)
        await self.config.guild(guild).tracked_member.set(None)

    def cog_unload(self):
        ...
