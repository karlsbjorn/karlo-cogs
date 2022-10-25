import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import discord.ui

from raidtools.emojis import button_emojis, class_emojis, spec_emojis
from raidtools.playerclasses import PlayerClasses, player_specs, spec_roles
from raidtools.shared import create_event_embed

log = logging.getLogger("red.karlo-cogs.raidtools")


class EventCreateView(discord.ui.View):
    def __init__(self, config):
        self.config = config
        super().__init__()

    @discord.ui.button(label="Kreiraj event", style=discord.ButtonStyle.primary)
    async def create_event(
        self, interaction: discord.Interaction, button: discord.ui.Button, /
    ) -> None:
        await interaction.response.send_modal(EventCreateModal(self.config))


class EventCreateModal(discord.ui.Modal):
    def __init__(self, config):
        self.config = config
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
        for player_class in PlayerClasses:
            player_class = player_class.value
            player_class = player_class.replace(" ", "_").lower()
            mock_signed_up[player_class] = [interaction.user.id]
        mock_signed_up["bench"] = [interaction.user.id]
        mock_signed_up["late"] = [interaction.user.id]
        mock_signed_up["tentative"] = [interaction.user.id]
        mock_signed_up["absent"] = [interaction.user.id]

        extras = {
            "event_name": str(self.event_name),
            "event_description": str(self.event_description),
            "event_date": str(self.event_date),
            "event_end_date": str(self.event_end_date),
            "event_guild": interaction.guild.id,
            "event_id": interaction.message.id,
        }
        embed = await create_event_embed(
            signed_up=mock_signed_up,
            event_info=extras,
            bot=interaction.client,
            config=self.config,
            preview_mode=True,
        )

        await interaction.response.send_message(
            content="Event će ovako izgledati:",
            embed=embed,
            view=EventPreviewView(extras=extras, config=self.config),
            ephemeral=True,
        )


class EventPreviewView(discord.ui.View):
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

        embed = await create_event_embed(
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

        # Send a Discord scheduled event
        try:
            scheduled_event = await self._add_scheduled_event(msg, interaction)
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

    async def _add_scheduled_event(
        self, event_message: discord.Message, interaction: discord.Interaction
    ) -> Optional[discord.ScheduledEvent]:
        """
        Add a Discord scheduled event to the guild.

        :param interaction: The interaction that triggered the event.
        :return: The Discord scheduled event.
        """
        try:
            parsed_start_timestamp = int(self.extras["event_date"][3:-3])
            parsed_end_timestamp = int(self.extras["event_end_date"][3:-3])
        except ValueError:
            return None

        event_start = datetime.fromtimestamp(parsed_start_timestamp, tz=timezone.utc)
        event_end = datetime.fromtimestamp(parsed_end_timestamp, tz=timezone.utc)

        event_message_link = (
            f"https://discord.com/channels/"
            f"{event_message.guild.id}/"
            f"{event_message.channel.id}/"
            f"{event_message.id}"
        )

        scheduled_event_description = (
            f"<a:ForTheAlliance:923196137626828821> "
            f"{interaction.user.mention}             "
            f"⌛ {discord.utils.format_dt(event_start, style='R')}\n\n"
            f"{event_message_link}\n\n"
            f"{self.extras['event_description']}"
        )

        scheduled_event = await interaction.guild.create_scheduled_event(
            name=self.extras["event_name"],
            description=scheduled_event_description,
            start_time=event_start,
            end_time=event_end,
            location="WoW Dragonflight",
        )
        return scheduled_event


class EventView(discord.ui.View):
    def __init__(self, config):
        self.config = config
        super().__init__(timeout=None)
        self.add_item(EventClassDropdown(self.config))

    @discord.ui.button(
        label="Bench", style=discord.ButtonStyle.grey, row=1, emoji=button_emojis["bench"]
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
        label="Kasnim", style=discord.ButtonStyle.grey, row=1, emoji=button_emojis["late"]
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
        label="Neodlučan", style=discord.ButtonStyle.grey, row=1, emoji=button_emojis["tentative"]
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
        label="Odsutan", style=discord.ButtonStyle.grey, row=1, emoji=button_emojis["absent"]
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
        embed = await create_event_embed(
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
                label=f"{player_class.value}",
                emoji=class_emojis[str(player_class.value).lower().replace(" ", "_")],
            )
            for player_class in PlayerClasses
        ]

        super().__init__(
            placeholder="Odaberi klasu",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        picked_class = self.values[0]
        event_id = str(interaction.message.id)
        await interaction.response.send_message(
            "Sad odaberi spec.",
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
                label=f"{spec.capitalize().replace('_', ' ')}",
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
        await self.config.guild(interaction.guild).events.set(current_events)
        await self.config.member(interaction.user).events.set(user_events)
        embed = await create_event_embed(
            signed_up=current_events[event_id]["signed_up"],
            event_info=current_events[event_id],
            bot=interaction.client,
            config=self.config,
        )
        event_msg = await interaction.channel.fetch_message(int(event_id))
        await event_msg.edit(embed=embed)
        await interaction.response.send_message("Uspješno si se prijavio.", ephemeral=True)
