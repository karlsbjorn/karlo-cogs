from typing import Dict, List

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("DiscordStreams", __file__)


@cog_i18n(_)
class DiscordStreams(commands.Cog):
    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=87446677010550784, force_registration=True)
        default_guild = {
            "alert_channels": [],
            "active_messages": {},
        }
        self.config.register_guild(**default_guild)

    @commands.command()
    @commands.guild_only()
    async def golivealert(self, ctx: commands.Context, channel: discord.TextChannel = None):
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
        else:
            alert_channels.append(channel.id)
            await self.config.guild(ctx.guild).alert_channels.set(alert_channels)
            await ctx.send(
                _("Go Live alerts will be sent to {channel}").format(channel=channel.mention)
            )

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        member_guild: discord.Guild = member.guild
        guild_config: Dict = await self.config.guild(member_guild).all()
        enabled = bool(guild_config["alert_channels"])

        if not enabled or await self.bot.cog_disabled_in_guild(self, member_guild) or member.bot:
            return

        # Stream ended
        if not after.self_stream:
            active_messages: Dict = guild_config["active_messages"]
            member_id = str(member.id)
            if member_id not in active_messages.keys():
                return

            alert_channels: List = guild_config["alert_channels"]
            for channel_id in alert_channels:
                channel: discord.TextChannel = member_guild.get_channel(channel_id)
                if not channel:  # Channel was deleted
                    channels = alert_channels
                    channels.remove(channel_id)
                    await self.config.guild(member_guild).alert_channels.set(channels)
                    continue

                live_message = active_messages[member_id]
                try:
                    message: discord.Message = await channel.fetch_message(live_message)
                    await message.delete()
                except discord.NotFound:  # Message was already deleted
                    messages: Dict = guild_config["active_messages"]
                    messages.pop(member_id)
                    await self.config.guild(member_guild).active_messages.set(messages)

        # Stream started
        if (not before.self_stream) and after.self_stream:
            channels_to_send_to = await self.config.guild(member_guild).alert_channels()
            stream = DiscordStream(after.channel, member)

            embed = stream.make_embed()
            for channel_id in channels_to_send_to:
                channel: discord.TextChannel = member_guild.get_channel(channel_id)
                if channel is None:
                    channels_to_send_to.remove(channel_id)
                    await self.config.guild(member_guild).alert_channels.set(channels_to_send_to)
                    continue

                message = await channel.send(
                    content=_("{member} is live!").format(member=member.display_name), embed=embed
                )
                await self.config.guild(member_guild).active_messages.set_raw(
                    str(member.id), value=message.id
                )
        return


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
        member = self.member
        voice_channel = self.voice_channel

        member_activity = None
        for activity in member.activities:
            if isinstance(activity, discord.Game):
                member_activity = activity.name
                break

        embed = discord.Embed(
            title=member.display_name,
            color=discord.Color.blurple(),
            description=voice_channel.mention,
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(
            text=_("Playing: {activity}").format(
                activity=member_activity if member_activity else _("Nothing")
            )
        )

        return embed
