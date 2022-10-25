from typing import Dict

import discord.ui


class DeleteConfirmationView(discord.ui.View):
    def __init__(self, config, event_id):
        self.config = config
        self.event_id = event_id
        super().__init__()

    @discord.ui.button(label="Da", style=discord.ButtonStyle.danger)
    async def confirmed_delete_event(
        self, interaction: discord.Interaction, button: discord.ui.Button, /
    ) -> None:
        events: Dict = await self.config.guild(interaction.guild).events()
        event_channel = interaction.guild.get_channel_or_thread(
            events[self.event_id]["event_channel"]
        )

        # Remove event message
        event_message = await event_channel.fetch_message(self.event_id)
        await event_message.delete()

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Event je izbrisan.", view=self)

        # Remove scheduled event if there is one
        scheduled_event_id = events[self.event_id].get("scheduled_event_id")
        if scheduled_event_id:
            scheduled_event = await interaction.guild.fetch_scheduled_event(scheduled_event_id)
            await scheduled_event.delete()

        # Remove from config
        events.pop(self.event_id)
        await self.config.guild(interaction.guild).events.set(events)

    @discord.ui.button(label="Ne", style=discord.ButtonStyle.success)
    async def cancel_delete_event(
        self, interaction: discord.Interaction, button: discord.ui.Button, /
    ) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
