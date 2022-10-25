import discord
from discord import app_commands

from views import event_create, event_manage


class SlashCommands:
    @app_commands.command(
        name="create",
        description="Kreiraj novi event u ovom kanalu.",
    )
    @app_commands.guilds(133049272517001216, 742457855008964800, 362298824854863882)
    @app_commands.guild_only()
    async def slash_event_create(self, interaction: discord.Interaction):
        # Don't do anything if the user doesn't have manage guild permission
        if (  # TODO: Add a role check too
            not interaction.user.guild_permissions.manage_guild
            and not await interaction.client.is_owner(interaction.user)
        ):
            await interaction.response.send_message(
                "Nemaš dozvolu za kreiranje eventa u ovom guildu.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Kreirajmo event!",
            description="Upute za kreiranje eventa:",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Naziv eventa", value="Unesi naziv", inline=False)
        embed.add_field(name="Opis eventa", value="Unesi opis", inline=False)
        embed.add_field(
            name="Datum eventa",
            value="**PROČITAJ ME**\n"
            "Unesi datum kao [vremensku oznaku koju možeš dobit ovdje.]"
            "(https://r.3v.fi/discord-timestamps/)\n"
            "Klikni gumb nakon što imaš vremensku oznaku kopiranu.",
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed, ephemeral=True, view=event_create.EventCreateView(self.config)
        )

    @app_commands.command(name="manage", description="Upravljaj eventima.")
    @app_commands.guilds(133049272517001216, 742457855008964800, 362298824854863882)
    @app_commands.guild_only()
    async def slash_event_manage(self, interaction: discord.Interaction):
        # Don't do anything if the user doesn't have manage guild permission
        if (  # TODO: Add a role check too
            not interaction.user.guild_permissions.manage_guild
            and not await interaction.client.is_owner(interaction.user)
        ):
            await interaction.response.send_message(
                "Nemaš dozvolu za upravljanje eventima u ovom guildu.", ephemeral=True
            )
            return

        events = await self.config.guild(interaction.guild).events()
        if not events:
            await interaction.response.send_message(
                "U ovom guildu nema aktivnih eventa.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Odaberi event kojim želiš upravljati.",
            ephemeral=True,
            view=event_manage.EventManageView(self.config, events=events),
        )
