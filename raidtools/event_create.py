import logging
from typing import Dict, Optional

import discord.ui

from raidtools.discordevent import RaidtoolsDiscordEvent
from raidtools.emojis import button_emojis, class_emojis, role_emojis, spec_emojis
from raidtools.playerclasses import player_classes, player_specs, spec_roles
from raidtools.shared import EventEmbed

log = logging.getLogger("red.karlo-cogs.raidtools")


class EventCreateView(discord.ui.View):
    def __init__(self, config, extra_buttons):
        self.config = config
        self.extra_buttons: str = extra_buttons
        super().__init__()

    @discord.ui.button(label="Kreiraj event", style=discord.ButtonStyle.primary)
    async def create_event(
        self, interaction: discord.Interaction, button: discord.ui.Button, /
    ) -> None:
        await interaction.response.send_modal(EventCreateModal(self.config, self.extra_buttons))


class EventCreateModal(discord.ui.Modal):
    def __init__(self, config, extra_buttons):
        self.config = config
        self.extra_buttons: str = extra_buttons
        self.title = "Kreirajmo event!"
        super().__init__(timeout=600, title=self.title)

        self.event_name = discord.ui.TextInput(
            label="Naziv eventa",
            style=discord.TextStyle.short,
            placeholder="Sepulcher of the First Ones",
            min_length=1,
            max_length=100,
        )
        self.event_description = discord.ui.TextInput(
            label="Opis eventa",
            style=discord.TextStyle.long,
            placeholder="SotFO HC, ako je moguće, 11/11",
            max_length=300,
        )
        self.event_date = discord.ui.TextInput(
            label="Datum eventa",
            style=discord.TextStyle.short,
            placeholder="<t:1665464280:R> (pročitaj upute)",
            min_length=1,
            max_length=20,
        )
        self.event_end_date = discord.ui.TextInput(
            label="Datum završetka eventa",
            style=discord.TextStyle.short,
            placeholder="<t:1823764123:R> (pročitaj upute)",
            min_length=1,
            max_length=20,
        )

        self.add_item(self.event_name)
        self.add_item(self.event_description)
        self.add_item(self.event_date)
        self.add_item(self.event_end_date)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        if not self.event_name:
            await interaction.response.send_message("Nisi unio naziv eventa.", ephemeral=True)
            return

        mock_signed_up = {}
        for player_class in player_classes:
            mock_signed_up[player_class] = [interaction.user.id]
        if self.extra_buttons == "buttons":
            mock_signed_up["bench"] = [interaction.user.id]
            mock_signed_up["late"] = [interaction.user.id]
            mock_signed_up["tentative"] = [interaction.user.id]
            mock_signed_up["absent"] = [interaction.user.id]
        elif self.extra_buttons == "offspec_buttons":
            mock_signed_up["offspec_tank"] = [interaction.user.id]
            mock_signed_up["offspec_healer"] = [interaction.user.id]
            mock_signed_up["offspec_dps"] = [interaction.user.id]
            mock_signed_up["offspec_rdps"] = [interaction.user.id]

        extras = {
            "event_name": str(self.event_name),
            "event_description": str(self.event_description),
            "event_date": str(self.event_date),
            "event_end_date": str(self.event_end_date),
            "event_guild": interaction.guild.id,
            "event_id": interaction.message.id,
        }
        embed = await EventEmbed.create_event_embed(
            signed_up=mock_signed_up,
            event_info=extras,
            bot=interaction.client,
            config=self.config,
            preview_mode=True,
        )

        view = None
        if self.extra_buttons == "no_buttons":
            view = EventPreviewView(extras=extras, config=self.config)
        elif self.extra_buttons == "buttons":
            view = EventPreviewWithButtonsView(extras=extras, config=self.config)
        elif self.extra_buttons == "offspec_buttons":
            view = EventPreviewWithOffspecButtonsView(extras=extras, config=self.config)

        await interaction.response.send_message(
            content="Event će ovako izgledati:",
            embed=embed,
            view=view,
            ephemeral=True,
        )


class EventPreviewView(discord.ui.View):
    def __init__(self, extras: Dict[str, Optional[str]], config):
        self.config = config
        super().__init__()
        self.extras = extras
        self.add_item(EventClassDropdown(self.config, disabled=True))

    @discord.ui.button(label="Potvrdi event", style=discord.ButtonStyle.green, row=1)
    async def confirm_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.post_event(interaction)

    async def post_event(self, interaction: discord.Interaction):
        mock_signed_up = {
            "warrior": [],
            "hunter": [],
            "mage": [],
            "priest": [],
            "rogue": [],
            "druid": [],
            "paladin": [],
            "warlock": [],
            "shaman": [],
            "monk": [],
            "demon_hunter": [],
            "death_knight": [],
            "evoker": [],
            "bench": [],
            "late": [],
            "tentative": [],
            "absent": [],
        }
        await interaction.response.edit_message(view=None)

        embed = await EventEmbed.create_event_embed(
            signed_up={},
            event_info=self.extras,
            bot=interaction.client,
            config=self.config,
        )

        channel_id = interaction.channel_id

        # Send event message
        msg = await interaction.client.get_channel(channel_id).send(
            embed=embed, view=EventView(self.config)
        )

        # Create a thread
        # try:
        #     await msg.create_thread(name=f"Rasprava - {self.extras['event_name']}")
        # except discord.Forbidden:
        #     log.debug(f"No permissions to create threads in {msg.channel.id} ({msg.guild})")
        # except discord.HTTPException:
        #     log.error("Failed to create thread", exc_info=True)

        # Send a Discord scheduled event
        try:
            scheduled_event = RaidtoolsDiscordEvent(msg, interaction, self.extras)
            scheduled_event = await scheduled_event.add_to_guild()
        except Exception as e:
            scheduled_event = None
            log.error(f"Failed to create scheduled event: {e}", exc_info=True)

        # Add event to config
        current_events: Dict = await self.config.guild(msg.guild).events()
        current_events[msg.id] = {
            "event_id": msg.id,
            "event_channel": msg.channel.id,
            "event_guild": msg.guild.id,
            "event_name": self.extras["event_name"],
            "event_description": self.extras["event_description"],
            "event_date": self.extras["event_date"],
            "event_end_date": self.extras["event_end_date"],
            "signed_up": mock_signed_up,
            "scheduled_event_id": scheduled_event.id if scheduled_event else None,
        }
        await self.config.guild(msg.guild).events.set(current_events)


class EventPreviewWithButtonsView(discord.ui.View):
    def __init__(self, extras: Dict[str, Optional[str]], config):
        self.config = config
        super().__init__()
        self.extras = extras
        self.add_item(EventClassDropdown(self.config, disabled=True))

    @discord.ui.button(
        label="Bench",
        style=discord.ButtonStyle.grey,
        disabled=True,
        row=1,
        emoji=button_emojis["bench"],
    )
    async def bench(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(
        label="Kasnim",
        style=discord.ButtonStyle.grey,
        disabled=True,
        row=1,
        emoji=button_emojis["late"],
    )
    async def late(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(
        label="Neodlučan",
        style=discord.ButtonStyle.grey,
        disabled=True,
        row=1,
        emoji=button_emojis["tentative"],
    )
    async def tentative(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(
        label="Odsutan",
        style=discord.ButtonStyle.grey,
        disabled=True,
        row=1,
        emoji=button_emojis["absent"],
    )
    async def no_show(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Potvrdi event", style=discord.ButtonStyle.green, row=3)
    async def confirm_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.post_event(interaction)

    async def post_event(self, interaction: discord.Interaction):
        mock_signed_up = {
            "warrior": [],
            "hunter": [],
            "mage": [],
            "priest": [],
            "rogue": [],
            "druid": [],
            "paladin": [],
            "warlock": [],
            "shaman": [],
            "monk": [],
            "demon_hunter": [],
            "death_knight": [],
            "evoker": [],
            "bench": [],
            "late": [],
            "tentative": [],
            "absent": [],
        }
        await interaction.response.edit_message(view=None)

        embed = await EventEmbed.create_event_embed(
            signed_up={},
            event_info=self.extras,
            bot=interaction.client,
            config=self.config,
        )

        channel_id = interaction.channel_id

        # Send event message
        msg = await interaction.client.get_channel(channel_id).send(
            embed=embed, view=EventWithButtonsView(self.config)
        )

        # Create a thread
        # try:
        #     await msg.create_thread(name=f"Rasprava - {self.extras['event_name']}")
        # except discord.Forbidden:
        #     log.debug(f"No permissions to create threads in {msg.channel.id} ({msg.guild})")
        # except discord.HTTPException:
        #     log.error("Failed to create thread", exc_info=True)

        # Send a Discord scheduled event
        try:
            scheduled_event = RaidtoolsDiscordEvent(msg, interaction, self.extras)
            scheduled_event = await scheduled_event.add_to_guild()
        except Exception as e:
            scheduled_event = None
            log.error(f"Failed to create scheduled event: {e}", exc_info=True)

        # Add event to config
        current_events: Dict = await self.config.guild(msg.guild).events()
        current_events[msg.id] = {
            "event_id": msg.id,
            "event_channel": msg.channel.id,
            "event_guild": msg.guild.id,
            "event_name": self.extras["event_name"],
            "event_description": self.extras["event_description"],
            "event_date": self.extras["event_date"],
            "event_end_date": self.extras["event_end_date"],
            "signed_up": mock_signed_up,
            "scheduled_event_id": scheduled_event.id if scheduled_event else None,
        }
        await self.config.guild(msg.guild).events.set(current_events)


class EventPreviewWithOffspecButtonsView(discord.ui.View):
    def __init__(self, extras: Dict[str, Optional[str]], config):
        self.config = config
        super().__init__()
        self.extras = extras
        self.add_item(EventClassDropdown(self.config, disabled=True))

    @discord.ui.button(
        label="Offspec:",
        style=discord.ButtonStyle.grey,
        row=1,
        custom_id="raidtools:eventbutton:offspec",
        disabled=True,
    )
    async def offspec(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(
        style=discord.ButtonStyle.blurple,
        row=1,
        emoji=role_emojis["tank"],
        custom_id="raidtools:eventbutton:tank",
        disabled=True,
    )
    async def tank(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(
        style=discord.ButtonStyle.green,
        row=1,
        emoji=role_emojis["heal"],
        custom_id="raidtools:eventbutton:healer",
        disabled=True,
    )
    async def healer(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(
        style=discord.ButtonStyle.red,
        row=1,
        emoji=button_emojis["dps"],
        custom_id="raidtools:eventbutton:dps",
        disabled=True,
    )
    async def dps(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(
        style=discord.ButtonStyle.red,
        row=1,
        emoji=button_emojis["rdps"],
        custom_id="raidtools:eventbutton:rdps",
        disabled=True,
    )
    async def ranged_dps(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Potvrdi event", style=discord.ButtonStyle.green, row=3)
    async def confirm_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.post_event(interaction)

    async def post_event(self, interaction: discord.Interaction):
        mock_signed_up = {
            "warrior": [],
            "hunter": [],
            "mage": [],
            "priest": [],
            "rogue": [],
            "druid": [],
            "paladin": [],
            "warlock": [],
            "shaman": [],
            "monk": [],
            "demon_hunter": [],
            "death_knight": [],
            "evoker": [],
            "offspec_tank": [],
            "offspec_healer": [],
            "offspec_dps": [],
            "offspec_rdps": [],
        }
        await interaction.response.edit_message(view=None)

        embed = await EventEmbed.create_event_embed(
            signed_up={},
            event_info=self.extras,
            bot=interaction.client,
            config=self.config,
        )

        channel_id = interaction.channel_id

        # Send event message
        msg = await interaction.client.get_channel(channel_id).send(
            embed=embed, view=EventWithOffspecView(self.config)
        )

        # Create a thread
        # try:
        #     await msg.create_thread(name=f"Rasprava - {self.extras['event_name']}")
        # except discord.Forbidden:
        #     log.debug(f"No permissions to create threads in {msg.channel.id} ({msg.guild})")
        # except discord.HTTPException:
        #     log.error("Failed to create thread", exc_info=True)

        # Send a Discord scheduled event
        try:
            scheduled_event = RaidtoolsDiscordEvent(msg, interaction, self.extras)
            scheduled_event = await scheduled_event.add_to_guild()
        except Exception as e:
            scheduled_event = None
            log.error(f"Failed to create scheduled event: {e}", exc_info=True)

        # Add event to config
        current_events: Dict = await self.config.guild(msg.guild).events()
        current_events[msg.id] = {
            "event_id": msg.id,
            "event_channel": msg.channel.id,
            "event_guild": msg.guild.id,
            "event_name": self.extras["event_name"],
            "event_description": self.extras["event_description"],
            "event_date": self.extras["event_date"],
            "event_end_date": self.extras["event_end_date"],
            "signed_up": mock_signed_up,
            "scheduled_event_id": scheduled_event.id if scheduled_event else None,
        }
        await self.config.guild(msg.guild).events.set(current_events)


class EventView(discord.ui.View):
    def __init__(self, config):
        self.config = config
        super().__init__(timeout=None)
        self.add_item(EventClassDropdown(self.config))


class EventWithButtonsView(discord.ui.View):
    def __init__(self, config):
        self.config = config
        super().__init__(timeout=None)
        self.add_item(EventClassDropdown(self.config))

    @discord.ui.button(
        label="Bench",
        style=discord.ButtonStyle.grey,
        row=1,
        emoji=button_emojis["bench"],
        custom_id="raidtools:eventbutton:bench",
    )
    async def bench(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_events = await self.config.guild(interaction.guild).events()
        event_id = str(interaction.message.id)

        user_events: Dict = await self.config.member(interaction.user).events()
        if event_id not in user_events:
            user_events[event_id] = {
                "participating_role": None,
                "participating_class": None,
                "participating_spec": None,
            }

        user_this_event: Dict = user_events.get(event_id, {})

        user_participating_class: str = user_this_event.get("participating_class", None)

        bench_participants = current_events[event_id]["signed_up"]["bench"]
        if interaction.user.id in bench_participants:
            await interaction.response.send_message("Već si benchan.", ephemeral=True)
        else:
            # Remove user from the class they were signed up for
            if user_participating_class:
                current_events[event_id]["signed_up"][user_participating_class.lower()].remove(
                    interaction.user.id
                )

            current_events[event_id]["signed_up"]["bench"] += [interaction.user.id]

            user_events[event_id]["participating_class"] = "bench"
            user_events[event_id]["participating_role"] = None

            await self.update_event(current_events, event_id, interaction, user_events)
        return

    @discord.ui.button(
        label="Kasnim",
        style=discord.ButtonStyle.grey,
        row=1,
        emoji=button_emojis["late"],
        custom_id="raidtools:eventbutton:late",
    )
    async def late(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_events = await self.config.guild(interaction.guild).events()
        event_id = str(interaction.message.id)

        user_events: Dict = await self.config.member(interaction.user).events()
        if event_id not in user_events:
            user_events[event_id] = {"participating_class": None, "participating_spec": None}

        user_this_event: Dict = user_events.get(event_id, {})

        user_participating_class: str = user_this_event.get("participating_class", None)

        late_participants = current_events[event_id]["signed_up"]["late"]
        if interaction.user.id in late_participants:
            await interaction.response.send_message("Već kasniš.", ephemeral=True)
        else:
            # Remove user from the class they were signed up for
            if user_participating_class:
                current_events[event_id]["signed_up"][user_participating_class.lower()].remove(
                    interaction.user.id
                )

            current_events[event_id]["signed_up"]["late"] += [interaction.user.id]

            user_events[event_id]["participating_class"] = "late"

            await self.update_event(current_events, event_id, interaction, user_events)
        return

    @discord.ui.button(
        label="Neodlučan",
        style=discord.ButtonStyle.grey,
        row=1,
        emoji=button_emojis["tentative"],
        custom_id="raidtools:eventbutton:tentative",
    )
    async def tentative(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_events = await self.config.guild(interaction.guild).events()
        event_id = str(interaction.message.id)

        user_events: Dict = await self.config.member(interaction.user).events()
        if event_id not in user_events:
            user_events[event_id] = {"participating_class": None, "participating_spec": None}

        user_this_event: Dict = user_events.get(event_id, {})

        user_participating_class: str = user_this_event.get("participating_class", None)

        tentative_participants = current_events[event_id]["signed_up"]["tentative"]
        if interaction.user.id in tentative_participants:
            await interaction.response.send_message("Već si neodlučan.", ephemeral=True)
        else:
            # Remove user from the class they were signed up for
            if user_participating_class:
                current_events[event_id]["signed_up"][user_participating_class.lower()].remove(
                    interaction.user.id
                )

            current_events[event_id]["signed_up"]["tentative"] += [interaction.user.id]

            user_events[event_id]["participating_class"] = "tentative"
            user_events[event_id]["participating_role"] = None

            await self.update_event(current_events, event_id, interaction, user_events)
        return

    @discord.ui.button(
        label="Odsutan",
        style=discord.ButtonStyle.grey,
        row=1,
        emoji=button_emojis["absent"],
        custom_id="raidtools:eventbutton:absent",
    )
    async def absent(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_events = await self.config.guild(interaction.guild).events()
        event_id = str(interaction.message.id)

        user_events: Dict = await self.config.member(interaction.user).events()
        if event_id not in user_events:
            user_events[event_id] = {"participating_class": None, "participating_spec": None}

        user_this_event: Dict = user_events.get(event_id, {})

        user_participating_class: str = user_this_event.get("participating_class", None)

        no_show_participants = current_events[event_id]["signed_up"]["absent"]
        if interaction.user.id in no_show_participants:
            await interaction.response.send_message("Već si odsutan.", ephemeral=True)
        else:
            # Remove user from the class they were signed up for
            if user_participating_class:
                current_events[event_id]["signed_up"][user_participating_class.lower()].remove(
                    interaction.user.id
                )

            current_events[event_id]["signed_up"]["absent"] += [interaction.user.id]

            user_events[event_id]["participating_class"] = "absent"
            user_events[event_id]["participating_role"] = None

            await self.update_event(current_events, event_id, interaction, user_events)
        return

    async def update_event(self, current_events, event_id, interaction, user_events):
        await self.config.guild(interaction.guild).events.set(current_events)
        await self.config.member(interaction.user).events.set(user_events)
        embed = await EventEmbed.create_event_embed(
            signed_up=current_events[event_id]["signed_up"],
            event_info=current_events[event_id],
            bot=interaction.client,
            config=self.config,
        )
        await interaction.response.edit_message(embed=embed, view=self)


class EventWithOffspecView(discord.ui.View):
    def __init__(self, config):
        self.config = config
        super().__init__(timeout=None)
        self.add_item(EventClassDropdown(self.config))

    @discord.ui.button(
        label="Offspec:",
        style=discord.ButtonStyle.grey,
        row=1,
        custom_id="raidtools:eventbutton:offspec",
        disabled=True,
    )
    async def offspec(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(
        style=discord.ButtonStyle.blurple,
        row=1,
        emoji=role_emojis["tank"],
        custom_id="raidtools:eventbutton:tank",
    )
    async def tank(self, interaction: discord.Interaction, button: discord.ui.Button):
        log.debug(f"Tank button pressed by {interaction.user.name}")
        current_events = await self.config.guild(interaction.guild).events()
        event_id = str(interaction.message.id)

        user_events: Dict = await self.config.member(interaction.user).events()
        if event_id not in user_events:
            user_events[event_id] = {
                "participating_role": None,
                "participating_class": None,
                "participating_spec": None,
                "offspec_role": None,
            }

        user_this_event: Dict = user_events.get(event_id, {})
        user_participating_role: str = user_this_event.get("offspec_role", None)

        tank_offspec_members = current_events[event_id]["signed_up"]["offspec_tank"]
        if interaction.user.id in tank_offspec_members:
            await interaction.response.send_message("Već si Tank offspec.", ephemeral=True)
        elif not user_this_event.get("participating_class", None):
            await interaction.response.send_message(
                f"{interaction.user.mention} Prvo se moraš prijaviti za glavni spec.",
                ephemeral=True,
            )
        else:
            # Add user to the offspec role
            if user_participating_role:
                current_events[event_id]["signed_up"][user_participating_role.lower()].remove(
                    interaction.user.id
                )
            current_events[event_id]["signed_up"]["offspec_tank"] += [interaction.user.id]
            user_events[event_id]["offspec_role"] = "offspec_tank"
            await self.update_event(current_events, event_id, interaction, user_events)
        return

    @discord.ui.button(
        style=discord.ButtonStyle.green,
        row=1,
        emoji=role_emojis["heal"],
        custom_id="raidtools:eventbutton:healer",
    )
    async def healer(self, interaction: discord.Interaction, button: discord.ui.Button):
        log.debug(f"Healer button pressed by {interaction.user.name}")
        current_events = await self.config.guild(interaction.guild).events()
        event_id = str(interaction.message.id)

        user_events: Dict = await self.config.member(interaction.user).events()
        if event_id not in user_events:
            user_events[event_id] = {
                "participating_role": None,
                "participating_class": None,
                "participating_spec": None,
                "offspec_role": None,
            }

        user_this_event: Dict = user_events.get(event_id, {})
        user_participating_role: str = user_this_event.get("offspec_role", None)

        heal_offspec_members = current_events[event_id]["signed_up"]["offspec_healer"]
        if interaction.user.id in heal_offspec_members:
            await interaction.response.send_message("Već si Healer offspec.", ephemeral=True)
        elif not user_this_event.get("participating_class", None):
            await interaction.response.send_message(
                "Prvo se moraš prijaviti za glavni spec.", ephemeral=True
            )
        else:
            # Add user to the offspec role
            if user_participating_role:
                current_events[event_id]["signed_up"][user_participating_role.lower()].remove(
                    interaction.user.id
                )
            current_events[event_id]["signed_up"]["offspec_healer"] += [interaction.user.id]
            user_events[event_id]["offspec_role"] = "offspec_healer"
            await self.update_event(current_events, event_id, interaction, user_events)
        return

    @discord.ui.button(
        style=discord.ButtonStyle.red,
        row=1,
        emoji=button_emojis["dps"],
        custom_id="raidtools:eventbutton:dps",
    )
    async def dps(self, interaction: discord.Interaction, button: discord.ui.Button):
        log.debug(f"DPS button pressed by {interaction.user.name}")
        current_events = await self.config.guild(interaction.guild).events()
        event_id = str(interaction.message.id)

        user_events: Dict = await self.config.member(interaction.user).events()
        if event_id not in user_events:
            user_events[event_id] = {
                "participating_role": None,
                "participating_class": None,
                "participating_spec": None,
                "offspec_role": None,
            }

        user_this_event: Dict = user_events.get(event_id, {})
        user_participating_role: str = user_this_event.get("offspec_role", None)

        dps_offspec_members = current_events[event_id]["signed_up"]["offspec_dps"]
        if interaction.user.id in dps_offspec_members:
            await interaction.response.send_message("Već si DPS offspec.", ephemeral=True)
        elif not user_this_event.get("participating_class", None):
            await interaction.response.send_message(
                "Prvo se moraš prijaviti za glavni spec.", ephemeral=True
            )
        else:
            # Add user to the offspec role
            if user_participating_role:
                current_events[event_id]["signed_up"][user_participating_role.lower()].remove(
                    interaction.user.id
                )
            current_events[event_id]["signed_up"]["offspec_dps"] += [interaction.user.id]
            user_events[event_id]["offspec_role"] = "offspec_dps"
            await self.update_event(current_events, event_id, interaction, user_events)
        return

    @discord.ui.button(
        style=discord.ButtonStyle.red,
        row=1,
        emoji=button_emojis["rdps"],
        custom_id="raidtools:eventbutton:rdps",
    )
    async def ranged_dps(self, interaction: discord.Interaction, button: discord.ui.Button):
        log.debug(f"Ranged DPS button pressed by {interaction.user.name}")
        current_events = await self.config.guild(interaction.guild).events()
        event_id = str(interaction.message.id)

        user_events: Dict = await self.config.member(interaction.user).events()
        if event_id not in user_events:
            user_events[event_id] = {
                "participating_role": None,
                "participating_class": None,
                "participating_spec": None,
                "offspec_role": None,
            }

        user_this_event: Dict = user_events.get(event_id, {})
        user_participating_role: str = user_this_event.get("offspec_role", None)

        rdps_offspec_members = current_events[event_id]["signed_up"]["offspec_rdps"]
        if interaction.user.id in rdps_offspec_members:
            await interaction.response.send_message("Već si Ranged DPS offspec.", ephemeral=True)
        elif not user_this_event.get("participating_class", None):
            await interaction.response.send_message(
                "Prvo se moraš prijaviti za glavni spec.", ephemeral=True
            )
        else:
            # Add user to the offspec role
            if user_participating_role:
                current_events[event_id]["signed_up"][user_participating_role.lower()].remove(
                    interaction.user.id
                )
            current_events[event_id]["signed_up"]["offspec_rdps"] += [interaction.user.id]
            user_events[event_id]["offspec_role"] = "offspec_rdps"
            await self.update_event(current_events, event_id, interaction, user_events)
        return

    async def update_event(self, current_events, event_id, interaction, user_events):
        log.debug(f"Updating event {event_id} for {interaction.user.name}")
        await self.config.guild(interaction.guild).events.set(current_events)
        await self.config.member(interaction.user).events.set(user_events)
        embed = await EventEmbed.create_event_embed(
            signed_up=current_events[event_id]["signed_up"],
            event_info=current_events[event_id],
            bot=interaction.client,
            config=self.config,
        )
        await interaction.response.edit_message(embed=embed, view=self)


class EventClassDropdown(discord.ui.Select):
    def __init__(self, config, disabled: bool = False):
        self.config = config
        options = [
            discord.SelectOption(
                label=f"{player_class.replace('_', ' ').title()}",
                emoji=class_emojis[str(player_class)],
            )
            for player_class in player_classes
        ]

        super().__init__(
            placeholder="Odaberi klasu",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
            custom_id="raidtools:class-dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        log.debug(f"Class dropdown callback for {interaction.user.name}, picked {self.values}")
        picked_class = self.values[0]
        event_id = str(interaction.message.id)
        await interaction.response.send_message(
            f"{interaction.user.mention} Sad odaberi spec",
            ephemeral=True,
            view=EventSpecView(picked_class, self.config, event_id=event_id),
        )


class EventSpecView(discord.ui.View):
    def __init__(self, picked_class: str, config, event_id: str):
        super().__init__()
        self.add_item(EventSpecDropdown(picked_class, config, event_id=event_id))


class EventSpecDropdown(discord.ui.Select):
    def __init__(self, picked_class: str, config, event_id: str):
        self.config = config
        self.event_id = event_id
        self.picked_class = picked_class.lower().replace(" ", "_")
        class_specs = (spec for spec in player_specs[self.picked_class])
        options = [
            discord.SelectOption(
                label=f"{spec.capitalize().replace('_', ' ').title()}",
                emoji=spec_emojis[f"{self.picked_class}_{spec}"],
            )
            for spec in class_specs
        ]
        super().__init__(
            placeholder="Odaberi spec",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        log.debug(f"Spec dropdown callback for {interaction.user.name}, picked {self.values}")
        picked_spec = self.values[0]
        # Get player's current participation status
        current_events = await self.config.guild(interaction.guild).events()
        user_events = await self.config.member(interaction.user).events()

        user_this_event: Dict = user_events.get(self.event_id, None)
        if not user_this_event:
            user_events[self.event_id] = {
                "participating_role": None,
                "participating_class": None,
                "participating_spec": None,
            }
            user_this_event = user_events[self.event_id]

        user_participating_class: str = user_this_event.get("participating_class", None)

        # Remove user from the class they were signed up for
        if user_participating_class:
            current_events[self.event_id]["signed_up"][user_participating_class.lower()].remove(
                interaction.user.id
            )
            user_events[self.event_id]["participating_class"] = None

        # Add user to the class and spec they picked
        current_events[self.event_id]["signed_up"][self.picked_class] += [interaction.user.id]

        user_events[self.event_id]["participating_class"] = self.picked_class
        user_events[self.event_id]["participating_spec"] = picked_spec.lower()

        # Add user to the role of the spec they picked
        if picked_spec.lower() in spec_roles["tank"]:
            user_events[self.event_id]["participating_role"] = "tank"
        elif picked_spec.lower() in spec_roles["healer"]:
            user_events[self.event_id]["participating_role"] = "healer"
        else:
            user_events[self.event_id]["participating_role"] = "dps"

        await self.update_event(current_events, self.event_id, interaction, user_events)

    async def update_event(self, current_events, event_id, interaction, user_events):
        log.debug(f"Updating event {event_id} for {interaction.user.name}")
        await self.config.guild(interaction.guild).events.set(current_events)
        await self.config.member(interaction.user).events.set(user_events)
        embed = await EventEmbed.create_event_embed(
            signed_up=current_events[event_id]["signed_up"],
            event_info=current_events[event_id],
            bot=interaction.client,
            config=self.config,
        )
        event_msg = await interaction.channel.fetch_message(int(event_id))
        await event_msg.edit(embed=embed)
        await interaction.response.send_message("Uspješno si se prijavio.", ephemeral=True)
