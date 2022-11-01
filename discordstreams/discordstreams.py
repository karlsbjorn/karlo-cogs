import logging
from typing import Dict, List

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

log = logging.getLogger("red.karlo-cogs.discordstreams")
_ = Translator("DiscordStreams", __file__)


@cog_i18n(_)
class DiscordStreams(commands.Cog):
    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(
            self, identifier=87446677010550784, force_registration=True
        )
        default_guild = {
            "alert_channels": [],
            "active_messages": {},
        }
        self.config.register_guild(**default_guild)

    @commands.command()
    @commands.guild_only()
    async def golivealert(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Set the channel for live alerts."""
        if channel is None:
            channel = ctx.channel

        alert_channels = await self.config.guild(ctx.guild).alert_channels()
        if channel.id in alert_channels:
            alert_channels.remove(channel.id)
            await self.config.guild(ctx.guild).alert_channels.set(alert_channels)
            await ctx.send(
                _("Live alerts will no longer be sent to {channel}.").format(
                    channel=channel.mention
                )
            )
            await self._clean_up_config(channel, ctx)
        else:
            alert_channels.append(channel.id)
            await self.config.guild(ctx.guild).alert_channels.set(alert_channels)
            await ctx.send(
                _("Go Live alerts will be sent to {channel}").format(
                    channel=channel.mention
                )
            )

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        member_guild: discord.Guild = member.guild
        guild_config: Dict = await self.config.guild(member_guild).all()
        enabled = bool(guild_config["alert_channels"])

        if (
            not enabled
            or await self.bot.cog_disabled_in_guild(self, member_guild)
            or member.bot
        ):
            return

        # Stream ended
        if before.self_stream and not (after.channel and after.self_stream):
            active_messages: Dict = guild_config["active_messages"]
            member_id = str(member.id)
            if member_id not in active_messages:
                return

            await self._remove_stream_alerts(
                active_messages, guild_config, member_guild, member_id
            )
            return

        # Stream started
        if not (before.channel and before.self_stream) and after.self_stream:
            await self._send_stream_alerts(member, after)
            return

    async def _remove_stream_alerts(
        self, active_messages, guild_config, member_guild, member_id
    ) -> None:
        """
        Remove the stream alerts for a member.

        :param active_messages: The active alert messages for the guild.
        :param guild_config: The guild's config info.
        :param member_guild: The guild the member is in.
        :param member_id: The ID of the member.
        :return:
        """
        alert_channels: List = guild_config["alert_channels"]
        for channel_id in alert_channels:
            channel: discord.TextChannel = member_guild.get_channel(channel_id)
            if not channel:  # Channel was deleted
                channels = alert_channels
                channels.remove(channel_id)
                await self.config.guild(member_guild).alert_channels.set(channels)
                continue

            try:
                message_id = active_messages[member_id][str(channel_id)]["message"]
            except KeyError:
                continue

            try:
                message: discord.Message = await channel.fetch_message(message_id)
                await message.delete()
                active_messages[member_id].pop(str(channel_id))
            except discord.NotFound:  # Message was already deleted
                active_messages[member_id].pop(str(channel_id))

            if not active_messages[member_id]:
                # No more active messages for this member
                active_messages.pop(member_id)
        await self.config.guild(member_guild).active_messages.set(active_messages)

    async def _send_stream_alerts(
        self, member: discord.Member, after: discord.VoiceState
    ) -> None:
        """
        Send a message to the alert channels when a member starts streaming.

        :param member: The member who started streaming.
        :param after: The member's voice state after starting their stream.
        :return: None
        """
        member_guild: discord.Guild = member.guild
        channels_to_send_to = await self.config.guild(member_guild).alert_channels()

        stream = DiscordStream(after.channel, member)
        embed = stream.make_embed()

        active_messages = await self.config.guild(member_guild).active_messages()
        for channel_id in channels_to_send_to:
            channel: discord.TextChannel = member_guild.get_channel(channel_id)
            if channel is None:
                channels_to_send_to.remove(channel_id)
                await self.config.guild(member_guild).alert_channels.set(
                    channels_to_send_to
                )
                continue

            message = await channel.send(
                content=_("{member} is live!").format(member=member.display_name),
                embed=embed,
            )

            member_id = str(member.id)
            channel_id = str(channel_id)

            # Make the keys if they don't exist
            if member_id not in active_messages:
                active_messages[member_id] = {}
            if channel_id not in active_messages[member_id]:
                active_messages[member_id][channel_id] = {}

            active_messages[member_id][channel_id]["message"] = message.id

        await self.config.guild(member_guild).active_messages.set(active_messages)

    async def _clean_up_config(self, channel, ctx):
        active_messages: Dict = await self.config.guild(ctx.guild).active_messages()
        active_messages[str(ctx.author.id)].pop(str(channel.id))
        await self.config.guild(ctx.guild).active_messages.set(active_messages)


class DiscordStream:
    def __init__(self, voice_channel: discord.VoiceChannel, member: discord.Member):
        """
        A class to represent a Discord "Go Live" stream.

        :param voice_channel: Voice channel where the stream is taking place
        :param member: The member who started the stream
        """
        self.voice_channel = voice_channel
        self.member = member

    def make_embed(self) -> discord.Embed:
        zws = "\N{ZERO WIDTH SPACE}"
        member = self.member
        voice_channel = self.voice_channel

        member_activity = None
        for activity in member.activities:
            if activity.type == discord.ActivityType.playing:
                member_activity = activity.name
                break

        embed = discord.Embed(
            title=member.display_name,
            color=discord.Color.blurple(),
            description=f"{voice_channel.mention}",
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(
            name=zws,
            value=_("Stream started {relative_timestamp}").format(
                relative_timestamp=discord.utils.format_dt(
                    discord.utils.utcnow(), style="R"
                )
            ),
        )
        embed.set_footer(
            text=_("Playing: {activity}").format(
                activity=member_activity if member_activity else _("Nothing")
            )
        )

        return embed
