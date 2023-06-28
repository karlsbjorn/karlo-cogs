import logging
from dataclasses import dataclass

import discord
from bs4 import BeautifulSoup
from discord import app_commands
from rapidfuzz import fuzz
from redbot.core.i18n import Translator

_ = Translator("WoWTools", __file__)
log = logging.getLogger("red.karlo-cogs.wowtools")


class CVarSelect(discord.ui.Select):
    def __init__(self, cvars: list, current_cvar: str, author: int, message: discord.Message):
        self.cvars = cvars
        self.current_cvar = current_cvar
        self.author = author
        self.message = message

        options = [
            discord.SelectOption(
                label=cvar.name, value=cvar.name, description=cvar.description[:100]
            )
            for cvar in cvars
        ]
        if current_cvar:
            options = sorted(
                options, key=lambda x: fuzz.partial_ratio(x.value, current_cvar), reverse=True
            )
        else:
            # Sort by name
            options = sorted(options, key=lambda x: x.value)
        super().__init__(placeholder=_("Select a CVar"), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        cvar = self.values[0]
        cvar: CVar = next((cvar_obj for cvar_obj in self.cvars if cvar_obj.name == cvar))

        embed = discord.Embed(
            title=cvar.name,
            description=cvar.description,
            color=interaction.message.embeds[0].color,
        )
        if cvar.default:
            if cvar.default is False:
                default = _("No")
            elif cvar.default is True:
                default = _("Yes")
            else:
                default = cvar.default
            embed.add_field(
                name=_("Default"),
                value=default,
                inline=False,
            )
        if cvar.category:
            embed.add_field(name=_("Category"), value=cvar.category, inline=False)
        if cvar.scope:
            embed.add_field(name=_("Scope"), value=cvar.scope)
        if cvar.version:
            embed.add_field(name=_("Introduced in"), value=cvar.version, inline=False)

        if isinstance(cvar.default, bool):
            content = f"Enable: `/console {cvar.name} 1`\nDisable: `/console {cvar.name} 0`"
        await interaction.response.edit_message(
            content=content,
            embed=embed,
            view=CVarView(self.cvars, cvar.name, interaction.user.id, self.message),
        )


class CVarView(discord.ui.View):
    def __init__(self, cvars, current_cvar, author, message=None):
        super().__init__()
        self.author: int = author
        self.message: discord.Message = message
        self.add_item(CVarSelect(cvars, current_cvar, author, message))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.author:
            await interaction.response.send_message(
                _("You are not authorized to interact with this."), ephemeral=True
            )
            return False
        return True


@dataclass
class CVar:
    name: str
    default: bool | str | int | float
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
        """Get information about a WoW Console Variable"""
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
        if cvar.default:
            if cvar.default is False:
                default = _("No")
            elif cvar.default is True:
                default = _("Yes")
            else:
                default = cvar.default
            embed.add_field(
                name=_("Default"),
                value=default,
                inline=False,
            )
        if cvar.category:
            embed.add_field(name=_("Category"), value=cvar.category)
        if cvar.scope:
            embed.add_field(name=_("Scope"), value=cvar.scope)
        if cvar.version:
            embed.add_field(name=_("Introduced in"), value=cvar.version, inline=False)

        view = CVarView(self.cvar_cache, cvar.name, interaction.user.id)
        content = f"Enable: `/console {cvar.name} 1`\nDisable: `/console {cvar.name} 0`"
        view.message = await interaction.response.send_message(
            content=content,
            embed=embed,
            view=view,
        )

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
            version = cells[0].text.replace("\n", "").strip()
            name = cells[2].text.replace("\n", "").strip()
            default = cells[3].text.replace("\n", "").strip()
            if default == "1":
                default = True
            elif default == "0":
                default = False
            category = cells[4].text.replace("\n", "").strip()
            scope = cells[5].text.replace("\n", "").strip()
            description = cells[6].text.strip()
            cvars.append(CVar(name, default, category, scope, description, version))
        return cvars
