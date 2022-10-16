from typing import Dict, Optional

import discord.ui

from raidtools.emojis import button_emojis, class_emojis, spec_emojis
from raidtools.playerclasses import PlayerClasses, player_specs, spec_roles
from raidtools.shared import create_event_embed


class CreateEventView(discord.ui.View):
    def __init__(self, config):
        self.config = config
        super().__init__()

    @discord.ui.button(label="Kreiraj event", style=discord.ButtonStyle.primary)
    async def create_event(
        self, interaction: discord.Interaction, button: discord.ui.Button, /
    ) -> None:
        await interaction.response.send_modal(CreateEventModal(self.config))


class CreateEventModal(discord.ui.Modal):
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
            placeholder="<t:1665464280:R>",
            max_length=100,
        )

        self.add_item(self.event_name)
        self.add_item(self.event_description)
        self.add_item(self.event_date)

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


class ManageEventView(discord.ui.View):
    def __init__(self, config, events):
        self.config = config
        self.events = events
        super().__init__()
        self.add_item(ManageEventDropdown(self.config, events=events))


class ManageEventDropdown(discord.ui.Select):
    def __init__(self, config, events):
        self.config = config
        self.events = events
        options = [
            discord.SelectOption(
                label=event["event_name"], description=f"ID: {event_id}", value=event_id
            )
            for event_id, event in events.items()
        ]

        super().__init__(placeholder="Odaberi event", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        event_id = self.values[0]
        event = self.events[event_id]
        embed = await create_event_embed(
            signed_up=event["signed_up"],
            event_info=event,
            bot=interaction.client,
            config=self.config,
        )
        await interaction.response.send_message(
            content="Uređuješ ovaj event:",
            embed=embed,
            view=EventEditView(
                event_id=event_id, config=self.config, preview_msg=interaction.message
            ),
            ephemeral=True,
        )


class EventEditView(discord.ui.View):
    def __init__(self, event_id, config, preview_msg: discord.Message):
        self.event_id = event_id
        self.config = config
        super().__init__()
        self.add_item(EventEditDropdown(event_id=event_id, config=config, preview_msg=preview_msg))

    @discord.ui.button(label="Izbriši event", style=discord.ButtonStyle.danger, row=1)
    async def delete_event(
        self, interaction: discord.Interaction, button: discord.ui.Button, /
    ) -> None:
        await interaction.response.send_message(
            "Jesi siguran?",
            ephemeral=True,
            view=DeleteConfirmationView(self.config, self.event_id),
        )


class EventEditDropdown(discord.ui.Select):
    def __init__(self, event_id, config, preview_msg: discord.Message):
        self.event_id = event_id
        self.config = config
        self.preview_msg = preview_msg
        options = [
            discord.SelectOption(label="Uredi naziv i opis", value="edit_name"),
            discord.SelectOption(label="Uredi vrijeme eventa", value="edit_time"),
        ]

        super().__init__(placeholder="Odaberi radnju", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "edit_name":
            await interaction.response.send_modal(
                EventEditNameModal(
                    event_id=self.event_id, config=self.config, preview_msg=self.preview_msg
                )
            )
        elif self.values[0] == "edit_time":
            await interaction.response.send_modal(
                EventEditTimeModal(
                    event_id=self.event_id, config=self.config, preview_msg=self.preview_msg
                )
            )


class EventEditNameModal(discord.ui.Modal):
    def __init__(self, event_id, config, preview_msg: discord.Message):
        self.event_id = event_id
        self.config = config
        self.preview_msg = preview_msg
        self.title = "Uredi naziv i opis eventa"
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
            min_length=1,
            max_length=300,
        )

        self.add_item(self.event_name)
        self.add_item(self.event_description)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        events: Dict = await self.config.guild(interaction.guild).events()

        event = events[self.event_id]
        event["event_name"] = str(self.event_name)
        event["event_description"] = str(self.event_description)
        events[self.event_id] = event

        await self.config.guild(interaction.guild).events.set(events)

        # Update event
        embed = await create_event_embed(
            signed_up=event["signed_up"],
            event_info=event,
            bot=interaction.client,
            config=self.config,
        )
        event_channel = interaction.guild.get_channel_or_thread(event["event_channel"])
        event_msg = await event_channel.fetch_message(event["event_id"])
        await event_msg.edit(embed=embed)

        await interaction.response.send_message(
            "Naziv i opis eventa su promijenjeni.", ephemeral=True
        )


class EventEditTimeModal(discord.ui.Modal):
    raise NotImplementedError


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
        msg = await interaction.client.get_channel(channel_id).send(
            embed=embed, view=EventView(self.config)
        )

        current_events: Dict = await self.config.guild(msg.guild).events()
        current_events[msg.id] = {
            "event_id": msg.id,
            "event_channel": msg.channel.id,
            "event_guild": msg.guild.id,
            "event_name": self.extras["event_name"],
            "event_description": self.extras["event_description"],
            "event_date": self.extras["event_date"],
            "signed_up": mock_signed_up,
        }
        await self.config.guild(msg.guild).events.set(current_events)


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

        # Remove from config
        events.pop(self.event_id)
        await self.config.guild(interaction.guild).events.set(events)

        # Remove event message
        event_message = await event_channel.fetch_message(self.event_id)
        await event_message.delete()

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message("Event je izbrisan.", view=self)

    @discord.ui.button(label="Ne", style=discord.ButtonStyle.success)
    async def cancel_delete_event(
        self, interaction: discord.Interaction, button: discord.ui.Button, /
    ) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
