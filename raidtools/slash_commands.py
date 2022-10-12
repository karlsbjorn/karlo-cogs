import discord
from discord import app_commands

from raidtools.views import CreateEventView


class SlashCommands:
    @app_commands.command(
        name="create",
        description="Kreiraj novi event u ovom kanalu.",
    )
    @app_commands.guilds(133049272517001216, 742457855008964800)
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
            embed=embed, view=CreateEventView(self.config), ephemeral=True
        )
