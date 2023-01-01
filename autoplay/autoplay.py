import logging
from typing import Optional

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild

log = logging.getLogger("red.karlo-cogs.autoplay")
_ = Translator("AutoPlay", __file__)


@cog_i18n(_)
class AutoPlay(commands.Cog):
    """Automatically play music that a user is listening to on Spotify."""

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=87446677010550784, force_registration=True)
        default_guild = {"tracked_member": None}
        self.config.register_guild(**default_guild)

    @commands.command()
    @commands.guild_only()
    async def autoplay(self, ctx, member: discord.Member = None):
        """Set the member to track for autoplay."""
        if member is None:
            await self.config.guild(ctx.guild).tracked_member.set(None)
            await ctx.send(_("No longer tracking any member."))
        else:
            await self.config.guild(ctx.guild).tracked_member.set(member.id)
            await ctx.send(
                _("I'll now play whatever {member} is listening to.").format(member=member.mention)
            )

    @commands.Cog.listener("on_presence_update")
    async def _on_presence_update(self, before: discord.Member, after: discord.Member):
        if await self._member_checks(after):
            return
        if not (current_activity := self._get_spotify_activity(after)):
            return
        if (
            past_activity := self._get_spotify_activity(before)
        ) and past_activity.track_id == current_activity.track_id:
            return
        log.debug(
            f"Presence update detected.\n"
            f"{current_activity.track_id} - {current_activity.title}"
        )

        player = self.bot.lavalink.get_player(after.guild.id)
        if player is None:
            return
        track = await player.get_track(
            f"https://open.spotify.com/track/{current_activity.track_id}"
        )
        await player.play(
            query=f"https://open.spotify.com/track/{current_activity.track_id}",
            track=track,
            requester=after,
        )

    async def _member_checks(self, member) -> bool:
        return (
            member.id != tracked_member
            if (tracked_member := await self.config.guild(member.guild).tracked_member())
            else True
        )

    @staticmethod
    def _get_spotify_activity(member) -> Optional[discord.Spotify]:
        return next(
            (
                activity
                for activity in member.activities
                if activity.type == discord.ActivityType.listening
            ),
            None,
        )

    def cog_unload(self):
        ...
