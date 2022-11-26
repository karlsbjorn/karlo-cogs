from datetime import datetime, timezone
from typing import Optional

import discord


class RaidtoolsDiscordEvent:
    def __init__(self, event_message: discord.Message, interaction: discord.Interaction, extras):
        """
        Class for handling Discord events.

        :param event_message: The message that contains the event.
        :param interaction: The interaction that created the event.
        :param extras: Extra information about the event.
        """
        self.event_message = event_message
        self.interaction = interaction
        self.extras = extras

        self.event_start = None
        self.event_end = None

    async def add_to_guild(
        self,
    ) -> Optional[discord.ScheduledEvent]:
        """
        Add a Discord scheduled event to the guild.

        :return: The created Discord event, or None if not created.
        """
        try:
            parsed_start_timestamp = int(self.extras["event_date"][3:-3])
            parsed_end_timestamp = int(self.extras["event_end_date"][3:-3])
        except ValueError:
            return None

        self.event_start = datetime.fromtimestamp(parsed_start_timestamp, tz=timezone.utc)
        self.event_end = datetime.fromtimestamp(parsed_end_timestamp, tz=timezone.utc)

        try:
            scheduled_event = await self.interaction.guild.create_scheduled_event(
                name=self.extras["event_name"],
                description=self.event_description,
                start_time=self.event_start,
                end_time=self.event_end,
                location="WoW Dragonflight",
            )
        except ValueError:
            return None
        except discord.Forbidden:
            return None
        except discord.HTTPException:
            return None

        return scheduled_event

    async def edit_event(self) -> discord.ScheduledEvent:
        parsed_start_timestamp = int(self.extras["event_date"][3:-3])
        parsed_end_timestamp = int(self.extras["event_end_date"][3:-3])

        self.event_start = datetime.fromtimestamp(parsed_start_timestamp, tz=timezone.utc)
        self.event_end = datetime.fromtimestamp(parsed_end_timestamp, tz=timezone.utc)

        event = self.extras
        interaction = self.interaction

        event_name = event["event_name"]

        scheduled_event_id = event["scheduled_event_id"]
        if scheduled_event_id:
            scheduled_event = await interaction.guild.fetch_scheduled_event(scheduled_event_id)
            await scheduled_event.edit(
                name=event_name,
                description=self.event_description,
                start_time=scheduled_event.start_time,
                end_time=scheduled_event.end_time,
                location="WoW Dragonflight",
            )
            return scheduled_event
        else:
            raise ValueError("No scheduled event ID found.")

    @property
    def event_description(self):
        return (
            f"<a:ForTheAlliance:923196137626828821> "
            f"{self.interaction.user.mention}             "
            f"⌛ {discord.utils.format_dt(self.event_start, style='R')}\n\n"
            f"{self.event_link()}\n\n"
            f"{self.extras['event_description']}"
        )

    def event_link(self):
        return (
            f"https://discord.com/channels/"
            f"{self.event_message.guild.id}/"
            f"{self.event_message.channel.id}/"
            f"{self.event_message.id}"
        )
