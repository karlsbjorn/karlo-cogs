from aiolimiter import AsyncLimiter
import discord
from pylav.events.player import PlayerDisconnectedEvent, PlayerStoppedEvent
from pylav.events.track import TrackEndEvent, TrackResumedEvent, TrackStartEvent
from pylav.logging import getLogger
from pylav.players.player import Player
from pylav.type_hints.bot import DISCORD_BOT_TYPE
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

log = getLogger("PyLav.3rdpt.karlo-cogs.pylavchannelstatus")
_ = Translator("PyLavChannelStatus", __file__)


@cog_i18n(_)
class PyLavChannelStatus(commands.Cog):
    def __init__(self, bot: DISCORD_BOT_TYPE):
        self.bot: DISCORD_BOT_TYPE = bot
        # 5 every 5 seconds, pylav can be pretty spammy especially when playing a youtube playlist when the youtube source doesnt even work
        self.limiter = AsyncLimiter(5, 5)

    async def set_channel_status(self, event: TrackStartEvent | TrackResumedEvent):
        if not self.limiter.has_capacity():
            return
        player: Player = event.player
        channel = player.channel
        track_name = await event.track.get_track_display_name(
            max_length=500,
            author=True,
            unformatted=True,
            escape=False,
        )
        await self.limiter.acquire()
        await channel._edit(
            options={"status": track_name},
            reason=_("[PyLavChannelStatus] Setting channel status to new track"),
        )

    async def remove_channel_status(
        self, event: TrackEndEvent | PlayerDisconnectedEvent | PlayerStoppedEvent
    ):
        if not self.limiter.has_capacity():
            return
        player: Player = event.player
        channel = player.channel
        if player.current:
            return
        await self.limiter.acquire()
        try:
            await channel._edit(
                options={"status": None},
                reason=_("[PyLavChannelStatus] Removing channel status"),
            )
        except discord.Forbidden:
            return

    @commands.Cog.listener()
    async def on_pylav_track_start_event(self, event: TrackStartEvent):
        await self.set_channel_status(event)

    @commands.Cog.listener()
    async def on_pylav_track_resumed_event(self, event: TrackResumedEvent):
        await self.set_channel_status(event)

    @commands.Cog.listener()
    async def on_pylav_track_end_event(self, event: TrackEndEvent):
        await self.remove_channel_status(event)

    @commands.Cog.listener()
    async def on_pylav_player_disconnected_event(self, event: PlayerDisconnectedEvent):
        await self.remove_channel_status(event)

    @commands.Cog.listener()
    async def on_pylav_player_stopped_event(self, event: PlayerStoppedEvent):
        await self.remove_channel_status(event)
