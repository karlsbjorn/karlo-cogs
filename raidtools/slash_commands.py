import discord
from discord import app_commands

from raidtools.views import CreateEventView, ManageEventView


class SlashCommands:
    @app_commands.command(
        name="create",
        description="Kreiraj novi event u ovom kanalu.",
    )
    @app_commands.guilds(133049272517001216, 742457855008964800, 362298824854863882)
    @app_commands.guild_only()
    async def slash_event_create(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Kreirajmo event!",
            description="Upute za kreiranje eventa:",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Naziv eventa", value="Unesi naziv", inline=False)
        embed.add_field(name="Opis eventa", value="Unesi opis", inline=False)
        embed.add_field(
            name="Datum eventa",
            value="Unesi datum kao [vremensku oznaku](https://r.3v.fi/discord-timestamps/)",
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed, ephemeral=True, view=CreateEventView(self.config)
        )

    @app_commands.command(name="manage", description="Upravljaj eventima.")
    @app_commands.guilds(133049272517001216, 742457855008964800, 362298824854863882)
    @app_commands.guild_only()
    async def slash_event_manage(self, interaction: discord.Interaction):
        events = await self.config.guild(interaction.guild).events()
        if not events:
            await interaction.response.send_message(
                "U ovom guildu nema aktivnih eventa.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Odaberi event kojim želiš upravljati.",
            ephemeral=True,
            view=ManageEventView(self.config, events=events),
        )
