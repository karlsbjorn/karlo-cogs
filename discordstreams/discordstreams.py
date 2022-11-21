import logging
from datetime import datetime
from typing import Dict, List, Optional

import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild

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
        self.update_stream_messages.start()

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

    @tasks.loop(seconds=10)
    async def update_stream_messages(self):
        for guild in self.bot.guilds:
            if await self.bot.cog_disabled_in_guild(self, guild):
                continue
            await set_contextual_locales_from_guild(self.bot, guild)
            await self.update_guild_embeds(guild)

    @update_stream_messages.error
    async def update_stream_messages_error(self, error):
        log.error(
            f"Unhandled error in update_dungeon_scoreboard task: {error}", exc_info=True
        )

    async def update_guild_embeds(self, guild: discord.Guild) -> None:
        """
        Update the stream alert embeds for a guild.

        :param guild: The guild to update the embeds for.
        :return: None
        """
        active_messages: Dict = await self.config.guild(guild).active_messages()
        for member_id, message in active_messages.items():
            member: discord.Member = guild.get_member(int(member_id))
            if member is None:
                continue

            await self.update_message_embeds(guild, member, message)

    @staticmethod
    async def update_message_embeds(
        guild: discord.Guild, member: discord.Member, message: Dict
    ) -> None:
        """
        Update the stream alert embeds for a member.

        :param guild: The guild the member is in.
        :param member: The member to update the embeds for.
        :param message: Dictionary of messages to update and their channel IDs.
        :return: None
        """
        for channel_id, message_info in message.items():
            channel: discord.TextChannel = guild.get_channel(int(channel_id))
            if channel is None:
                continue

            message_id = message_info["message"]
            try:
                message: discord.Message = await channel.fetch_message(message_id)
            except discord.NotFound:
                log.error(
                    f"Message {message_id} not found in channel {channel_id}, skipping."
                )
                continue
            except discord.HTTPException:
                log.error(
                    f"Error fetching message {message_id} in {channel_id}, skipping.",
                    exc_info=True,
                )
                continue

            if member.voice is None:
                continue

            current_embed = message.embeds[0]
            current_embed_dict = current_embed.to_dict()

            stream = DiscordStream(member.voice.channel, member)

            new_embed = stream.make_embed(start_time=message.created_at)
            new_embed_dict = new_embed.to_dict()

            same_fields: bool = current_embed_dict["fields"] == new_embed_dict["fields"]
            same_footer: bool = current_embed_dict["footer"] == new_embed_dict["footer"]
            if same_fields and same_footer:
                # Don't edit if there's no change
                continue

            await message.edit(embed=new_embed)

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """
        Send or remove a stream alert when a member starts or stops streaming.

        :param member: The member who started or stopped streaming.
        :param before: The member's voice state before the change.
        :param after: The member's voice state after the change.
        :return: None
        """
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
        :return: None
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
        Send a message to the alert channels.

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

    def cog_unload(self) -> None:
        self.update_stream_messages.stop()


class DiscordStream:
    def __init__(self, voice_channel: discord.VoiceChannel, member: discord.Member):
        """
        A class to represent a Discord "Go Live" stream.

        :param voice_channel: Voice channel where the stream is taking place
        :param member: The member who started the stream
        """
        self.voice_channel = voice_channel
        self.member = member

    def make_embed(self, start_time: Optional[datetime] = None) -> discord.Embed:
        """
        Make an embed for the stream.

        :param start_time: The time the stream started. If None, the current time is used.
        :return: An embed showing the stream's details.
        """
        zws = "\N{ZERO WIDTH SPACE}"
        member = self.member
        voice_channel = self.voice_channel

        activity = self.get_activity()

        embed = discord.Embed(
            title=member.display_name,
            color=discord.Color.blurple(),
            description=f"{voice_channel.mention}",
        )
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        else:
            embed.set_thumbnail(url=member.default_avatar.url)

        embed.add_field(
            name=zws,
            value=_("Stream started {relative_timestamp}").format(
                relative_timestamp=discord.utils.format_dt(
                    discord.utils.utcnow(), style="R"
                )
                if not start_time
                else discord.utils.format_dt(start_time, style="R")
            ),
            inline=False,
        )

        details_msg = (
            ""
            + (f"{activity.details}\n" if activity.details else "")
            + (f"{activity.state}" if activity.state else "")
        )
        if details_msg:
            embed.add_field(
                name=_("Details"),
                value=details_msg,
            )

        embed.set_footer(text=_("Playing: {activity}").format(activity=activity.name))

        return embed

    def get_activity(self) -> discord.Activity:
        """
        Get the activity object relevant to the stream.

        :return: The activity object.
        """
        for activity in self.member.activities:
            if activity.type == discord.ActivityType.playing:
                return activity
        return discord.Activity(type=discord.ActivityType.playing, name=_("Nothing"))
