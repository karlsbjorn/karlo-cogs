import logging
from dataclasses import dataclass

import discord
from bs4 import BeautifulSoup
from discord import app_commands
from rapidfuzz import fuzz
from redbot.core.i18n import Translator

_ = Translator("WoWTools", __file__)
log = logging.getLogger("red.karlo-cogs.wowtools")


@dataclass
class CVar:
    name: str
    default: bool
    category: str
    scope: str
    description: str
    version: str


class CVarDocs:
    """WoW CVar documentation"""

    @app_commands.command(
        name="cvar",
        description="Get information about a WoW CVar",
    )
    async def slash_cvar(self, interaction: discord.Interaction, cvar: str):
        """Get information about a WoW CVar"""
        if not self.cvar_cache:
            self.cvar_cache = await self.get_all_cvars()

        cvar = next((cvar_obj for cvar_obj in self.cvar_cache if cvar_obj.name == cvar), None)
        if not cvar:
            return await interaction.response.send_message(
                _("No CVar found with that name."), ephemeral=True
            )

        embed = discord.Embed(
            title=cvar.name,
            description=cvar.description,
            color=await self.bot.get_embed_color(interaction.channel),
        )
        embed.add_field(
            name=_("Default"),
            value=_("Yes") if cvar.default else _("No"),
            inline=False,
        )
        if cvar.category:
            embed.add_field(name=_("Category"), value=cvar.category, inline=False)
        if cvar.scope:
            embed.add_field(name=_("Scope"), value=cvar.scope)
        if cvar.version:
            embed.add_field(name=_("Introduced in"), value=cvar.version, inline=False)

        content = f"Enable: `/console {cvar.name} 1`\nDisable: `/console {cvar.name} 0`"
        await interaction.response.send_message(content=content, embed=embed)

    @slash_cvar.autocomplete("cvar")
    async def slash_cvar_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not self.cvar_cache:
            self.cvar_cache = await self.get_all_cvars()

        choices = [
            app_commands.Choice(name=cvar.name, value=cvar.name) for cvar in self.cvar_cache
        ]

        if current:
            sorted_choices = sorted(
                choices, key=lambda x: fuzz.partial_ratio(x.value, current), reverse=True
            )
        else:
            # Sort by name
            sorted_choices = sorted(choices, key=lambda x: x.value)
        return sorted_choices[:25]

    async def get_all_cvars(self) -> list[CVar]:
        """Get all cvars from wowpedia"""
        log.info("Fetching all cvars from wowpedia")
        request_url = "https://wowpedia.fandom.com/wiki/Console_variables/Complete_list"
        async with self.session.request("GET", request_url) as resp:
            if resp.status != 200:
                log.error(f"Error fetching {request_url}: {resp.status}")
                return []
            soup = BeautifulSoup(await resp.text(), "html.parser")

        table = soup.find("table", {"class": "sortable"})
        if not table:
            log.error(f"Error fetching {request_url}: no table found")
            return []
        rows = table.find_all("tr")[1:]

        cvars = []
        for row in rows:
            cells = row.find_all("td")
            version = cells[0].text.replace("\n", "")
            name = cells[2].text.replace("\n", "")
            default = cells[3].text == "1"
            category = cells[4].text.replace("\n", "")
            scope = cells[5].text.replace("\n", "")
            description = cells[6].text.replace("\n", "")
            cvars.append(CVar(name, default, category, scope, description, version))
        return cvars
