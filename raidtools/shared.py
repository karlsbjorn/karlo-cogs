import logging
from typing import Dict, List, Union

import discord
from discord import Client
from redbot.core.bot import Red

from raidtools.emojis import (
    button_emojis,
    class_emojis,
    generic_emojis,
    role_emojis,
    spec_emojis,
)
from raidtools.playerclasses import player_classes

log = logging.getLogger("red.karlo-cogs.raidtools")


class EventEmbed:
    @staticmethod
    async def create_event_embed(
        signed_up: Dict[str, List[int]],
        event_info: dict,
        bot: Union[Client, Red],
        config,
        preview_mode: bool = False,
    ) -> discord.Embed:
        """
        Create an embed for the event.

        :param preview_mode: Whether the embed is for previewing the event.
        :param config: Red config to get member info from
        :param signed_up: A dictionary of classes and members who signed up for the event.
        :param event_info: Information about the event that can be added to the embed.
        :param bot: Bot instance
        :return: An embed for the event.
        """
        event_name: str = event_info["event_name"]
        event_description: str = event_info["event_description"]
        event_date: str = event_info["event_date"]
        event_end_date: str = event_info["event_end_date"]
        event_guild: discord.Guild = bot.get_guild(event_info["event_guild"])
        event_id = str(event_info["event_id"])

        # Reformat timestamps
        event_date = event_date.replace(":R>", ":F>")  # long date w/ day of week and short time
        event_end_date = event_end_date.replace(":R>", ":t>")  # short time

        # Check if all participants are still in the guild
        signed_up = await EventEmbed._filter_participants(config, event_guild, event_id, signed_up)

        zws = "\N{ZERO WIDTH SPACE}"
        embed = discord.Embed(
            description=f"ID: {event_id}\n" f"**{event_name}**\n" f"{event_description or None}\n",
            color=discord.Color.yellow(),
        )

        # Get the total number of members signed up for the event.
        primary_members, secondary_members = await EventEmbed._get_n_of_signups(signed_up)
        if secondary_members:
            embed.add_field(
                name=zws,
                value=f"{generic_emojis['signups']} **{len(primary_members)}** "
                f"(+{len(secondary_members)})\n"
                f"{generic_emojis['date']} {event_date} - {event_end_date}",
                inline=False,
            )
        else:
            embed.add_field(
                name=zws,
                value=f"{generic_emojis['signups']} "
                f"**{len(primary_members)}**\n"
                f"{generic_emojis['date']} "
                f"{event_date} - {event_end_date}",
                inline=False,
            )

        # Get the number of tanks, healers and dps signed up for the event.
        if not preview_mode:
            dps_n, healer_n, tank_n = await EventEmbed._get_n_of_roles(
                config, event_guild, event_id, signed_up
            )
        else:
            tank_n = 1
            healer_n = 1
            dps_n = 1

        # Add the number of tanks, healers and dps to the embed.
        await EventEmbed._add_n_of_roles(dps_n, embed, healer_n, tank_n, zws)

        # Add fields for each class that has a member signed up.
        await EventEmbed._add_signed_up_classes(
            config, embed, event_guild, event_id, preview_mode, signed_up
        )

        # Other statuses
        await EventEmbed._add_misc_fields(embed, event_guild, signed_up, zws)

        return embed

    @staticmethod
    async def _filter_participants(
        config, event_guild, event_id, signed_up: Dict[str, List[int]]
    ) -> Dict[str, List[int]]:
        """
        Check if all participants are still in the guild.

        :param config: Red config to get member info from
        :param event_guild: Guild the event is in
        :param event_id: ID of the event
        :param signed_up: A dictionary of classes and members who signed up for the event.
        :return: A dictionary of classes and members who signed up for the event with members who
         aren't in the guild anymore removed.
        """
        save_config = False
        for class_name, members in signed_up.items():
            for member_id in members:
                if not event_guild.get_member(member_id):
                    log.info(
                        f"Member {member_id} not in guild {event_guild.id}."
                        f"Wiping them from the event."
                    )
                    signed_up[class_name].remove(member_id)
                    save_config = True
        if save_config:
            log.info("A member was not in the guild. Saving config.")
            guild_events = await config.guild(event_guild).events()
            guild_events[event_id]["signed_up"] = signed_up

            await config.guild(event_guild).events.set(guild_events)
            log.info("Config saved.")
        return signed_up

    @staticmethod
    async def _get_n_of_signups(signed_up):
        primary_members = set()
        secondary_members = set()

        for class_name, members in signed_up.items():
            if class_name in ["bench", "tentative", "absent"]:
                continue
            elif class_name == "late":
                secondary_members.update(members)
                continue
            primary_members.update(members)

        return primary_members, secondary_members

    @staticmethod
    async def _add_signed_up_classes(
        config, embed, event_guild, event_id, preview_mode, signed_up
    ):
        for player_class in player_classes:
            if player_class in signed_up.keys() and len(signed_up[player_class]) > 0:
                signed_up_users = [member for member in signed_up[player_class]]

                value_str = ""
                if not preview_mode:
                    for user in signed_up_users:
                        user_obj = event_guild.get_member(user)
                        if not user_obj:
                            log.debug(f"User {user} not found in guild {event_guild.id}")
                            # TODO: Remove user from event config.
                            #  Consider other cases where `user_obj` might be `None`.
                            #  **Really** confirm that the user left the guild before removing
                            continue
                        member = await config.member(user_obj).events()
                        member_spec = member[event_id]["participating_spec"]
                        spec_emoji = f'{player_class}_{member_spec.replace(" ", "_").lower()}'
                        value_str += f"{spec_emojis[spec_emoji]} {user_obj.display_name}\n"
                    embed.add_field(
                        name=f"{class_emojis[player_class]} "
                        f"{player_class.replace('_', ' ').title()} "
                        f"({len(signed_up[player_class])})",
                        value=value_str,
                    )
                else:
                    embed.add_field(
                        name=f"{class_emojis[player_class]} "
                        f"{player_class.replace('_', ' ').title()} "
                        f"({len(signed_up[player_class])})",
                        value="\n".join(
                            [
                                event_guild.get_member(member).display_name
                                for member in signed_up[player_class]
                            ]
                        ),
                    )

    @staticmethod
    async def _add_n_of_roles(dps_n, embed, healer_n, tank_n, zws):
        embed.add_field(
            name=zws,
            value=f"{role_emojis['tank']} **{tank_n}** Tanks"
            if tank_n > 1 or tank_n == 0
            else f"{role_emojis['tank']} **{tank_n}** Tank",
        )
        embed.add_field(
            name=zws,
            value=f"{role_emojis['heal']} **{healer_n}** Healers"
            if healer_n > 1 or healer_n == 0
            else f"{role_emojis['heal']} **{healer_n}** Healer",
        )
        embed.add_field(
            name=zws,
            value=f"{role_emojis['dps']} **{dps_n}** DPS",
        )

    @staticmethod
    async def _add_misc_fields(embed, event_guild, signed_up, zws):
        if len(signed_up.get("bench", [])) > 0 or len(signed_up.get("late", [])) > 0:
            msg = ""
            if len(signed_up.get("bench", [])) > 0:
                msg += (
                    f"**{button_emojis['bench']} Bench ({len(signed_up['bench'])}): **"
                    f"{', '.join([event_guild.get_member(member).display_name for member in signed_up['bench']])}\n"
                )
            if len(signed_up.get("late", [])) > 0:
                msg += (
                    f"**{button_emojis['late']} Kasni ({len(signed_up['late'])}): **"
                    f"{', '.join([event_guild.get_member(member).display_name for member in signed_up['late']])}"
                )
            embed.add_field(
                name=zws,
                value=msg,
                inline=False,
            )
        if len(signed_up.get("tentative", [])) > 0 or len(signed_up.get("absent", [])) > 0:
            msg = ""
            if len(signed_up.get("tentative", [])) > 0:
                msg += (
                    f"**{button_emojis['tentative']} Neodlučan ({len(signed_up['tentative'])}): **"
                    f"{', '.join([event_guild.get_member(member).display_name for member in signed_up['tentative']])}\n"
                )
            if len(signed_up.get("absent", [])) > 0:
                msg += (
                    f"**{button_emojis['absent']} Odsutan ({len(signed_up['absent'])}): **"
                    f"{', '.join([event_guild.get_member(member).display_name for member in signed_up['absent']])}"
                )
            embed.add_field(
                name=zws,
                value=msg,
                inline=False,
            )

        if (
            len(signed_up.get("offspec_tank", [])) > 0
            or len(signed_up.get("offspec_healer", [])) > 0
        ):
            msg = ""
            if len(signed_up.get("offspec_tank", [])) > 0:
                msg += (
                    f"**{role_emojis['tank']} Tank Offspec ({len(signed_up['offspec_tank'])}): **"
                    f"{', '.join([event_guild.get_member(member).display_name for member in signed_up['offspec_tank']])}\n"
                )
            if len(signed_up.get("offspec_healer", [])) > 0:
                msg += (
                    f"**{role_emojis['heal']} Healer Offspec ({len(signed_up['offspec_healer'])}): **"
                    f"{', '.join([event_guild.get_member(member).display_name for member in signed_up['offspec_healer']])}"
                )
            embed.add_field(
                name=zws,
                value=msg,
                inline=False,
            )
        if len(signed_up.get("offspec_dps", [])) > 0 or len(signed_up.get("offspec_rdps", [])) > 0:
            msg = ""
            if len(signed_up.get("offspec_dps", [])) > 0:
                msg += (
                    f"**{role_emojis['dps']} DPS Offspec ({len(signed_up['offspec_dps'])}): **"
                    f"{', '.join([event_guild.get_member(member).display_name for member in signed_up['offspec_dps']])}\n"
                )
            if len(signed_up.get("offspec_rdps", [])) > 0:
                msg += (
                    f"**{role_emojis['rdps']} Ranged DPS Offspec ({len(signed_up['offspec_rdps'])}): **"
                    f"{', '.join([event_guild.get_member(member).display_name for member in signed_up['offspec_rdps']])}"
                )
            embed.add_field(
                name=zws,
                value=msg,
                inline=False,
            )

    @staticmethod
    async def _get_n_of_roles(config, event_guild, event_id, signed_up):
        tank_n = 0
        healer_n = 0
        dps_n = 0
        counted_users = []

        for player_class in signed_up:
            for user in signed_up[player_class]:
                if user in counted_users:
                    continue
                user_obj = event_guild.get_member(user)
                if not user_obj:
                    continue

                signee_event_info = await config.member(user_obj).events()
                if signee_event_info[event_id]["participating_role"] == "tank":
                    tank_n += 1
                elif signee_event_info[event_id]["participating_role"] == "healer":
                    healer_n += 1
                else:
                    dps_n += 1
                counted_users.append(user)
        return dps_n, healer_n, tank_n
