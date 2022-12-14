import logging
from datetime import datetime, timezone

import discord.utils
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

from .event_create import EventView, EventWithButtonsView, EventWithOffspecView
from .slash_commands import SlashCommands

log = logging.getLogger("red.karlo-cogs.raidtools")
_ = Translator("WoWTools", __file__)


@cog_i18n(_)
class RaidTools(SlashCommands, commands.Cog):
    """Create and manage WoW raid events for your guild."""

    def __init__(self, bot: Red):
        self.bot: Red = bot

        # Config
        self.config = Config.get_conf(self, identifier=87446677010550784)
        default_guild = {
            "events": {},
        }
        default_member = {
            "events": {},
        }
        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)

        # Persistent views
        log.debug("Adding persistent views")
        log.debug("Adding EventView")
        self.bot.add_view(EventView(self.config))
        log.debug("Adding EventWithButtonsView")
        self.bot.add_view(EventWithButtonsView(self.config))
        log.debug("Adding EventWithOffspecView")
        self.bot.add_view(EventWithOffspecView(self.config))

        # Background tasks
        self.check_events.start()

    @tasks.loop(minutes=15)
    async def check_events(self):
        """Check if any events have expired or started."""
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_data in all_guilds.items():
            for event_id, event_data in guild_data["events"].items():
                if event_data.get("event_started", None):
                    continue
                try:
                    event_date = int(event_data.get("event_date", None)[3:-3])
                except ValueError:
                    log.warning(f"Event {event_id} has no valid event_date. Skipping.")
                    continue
                except TypeError:
                    log.warning(f"Event {event_id} has no event_date. Skipping.")
                    continue
                if not event_date or len(str(event_date)) < 6:
                    continue

                try:
                    event_date = datetime.fromtimestamp(event_date, tz=timezone.utc)
                except OverflowError:
                    log.warning(f"Event {event_id} has no valid event_date. Skipping.")
                    continue

                now = discord.utils.utcnow()

                if now.timestamp() > event_date.timestamp():
                    # Event has started
                    guild = self.bot.get_guild(event_data["event_guild"])
                    if not guild:
                        log.warning(f"Guild {event_data['event_guild']} not found.")
                        continue
                    channel = guild.get_channel(event_data["event_channel"])
                    if not channel:
                        log.warning(
                            f"Channel {event_data['event_channel']} in guild {guild.id} not found."
                        )
                        continue
                    try:
                        message = await channel.fetch_message(event_data["event_id"])
                    except discord.NotFound:
                        # TODO: Remove event from config
                        log.warning(
                            f"Message {event_data['event_id']} in channel {channel.id} not found."
                        )
                        continue
                    except discord.Forbidden:
                        log.warning(
                            f"No permission to fetch message {event_data['event_id']} in channel {channel.id}."
                        )
                        continue
                    except discord.HTTPException:
                        log.warning(
                            f"Error fetching message {event_data['event_id']} in channel {channel.id}.",
                            exc_info=True,
                        )
                        continue
                    if not message:
                        log.warning(
                            f"Message {event_data['event_id']} in channel {channel.id} not found."
                        )
                        continue

                    # Close and lock the thread
                    if thread := guild.get_thread(message.id):
                        await thread.edit(locked=True, archived=True)

                    # Remove signup ability
                    await message.edit(view=None)

                    guild_data["events"][event_id]["event_started"] = True
                    await self.config.guild(guild).set(guild_data)

    def cog_unload(self):
        self.check_events.stop()
