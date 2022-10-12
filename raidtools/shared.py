from typing import Dict, List

import discord
from redbot.core.bot import Red

from raidtools.emojis import (
    button_emojis,
    class_emojis,
    generic_emojis,
    role_emojis,
    spec_emojis,
)
from raidtools.playerclasses import PlayerClasses


async def create_event_embed(
    signed_up: Dict[str, List[int]], event_info: dict, bot: Red, config, preview_mode: bool = False
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
    event_name = event_info["event_name"]
    event_description = event_info["event_description"]
    event_date = event_info["event_date"]
    event_guild = bot.get_guild(event_info["event_guild"])
    event_id = str(event_info["event_id"])

    zws = "\N{ZERO WIDTH SPACE}"
    embed = discord.Embed(
        title=event_name,
        description=f"{event_description if event_description else None}\n"
        f"{event_date if event_date else None}",
        color=discord.Color.yellow(),
    )

    # Get the total number of members signed up for the event.
    msg = ""
    primary_members = set()
    secondary_members = set()
    for class_name, members in signed_up.items():
        if class_name == "bench":
            continue
        elif class_name == "late":
            secondary_members.update(members)
            continue
        elif class_name == "tentative":
            continue
        elif class_name == "absent":
            continue
        primary_members.update(members)
    if secondary_members:
        embed.add_field(
            name=zws,
            value=f"{generic_emojis['signups']} "
            f"**{len(primary_members)}** "
            f"(+{len(secondary_members)})",
            inline=False,
        )
    else:
        embed.add_field(
            name=zws,
            value=f"{generic_emojis['signups']} " f"**{len(primary_members)}**",
            inline=False,
        )

    # Get the number of tanks, healers and dps signed up for the event.
    if not preview_mode:
        tank_n = 0
        healer_n = 0
        dps_n = 0
        for player_class in signed_up:
            for user in signed_up[player_class]:
                user_obj = event_guild.get_member(user)
                signee_event_info = await config.member(user_obj).events()
                if signee_event_info[event_id]["participating_role"] == "tank":
                    tank_n += 1
                elif signee_event_info[event_id]["participating_role"] == "healer":
                    healer_n += 1
                else:
                    dps_n += 1
    else:
        tank_n = 1
        healer_n = 1
        dps_n = 1

    # Add the number of tanks, healers and dps to the embed.
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
        value=f"{role_emojis['dps'] }**{dps_n}** DPS",
    )

    # Add fields for each class that has a member signed up.
    for player_class in PlayerClasses:
        player_class = str(player_class.value)
        player_class = player_class.replace(" ", "_").lower()
        if player_class in signed_up.keys() and len(signed_up[player_class]) > 0:
            signed_up_users = [member for member in signed_up[player_class]]
            value_str = ""
            if not preview_mode:
                for user in signed_up_users:
                    user_obj = event_guild.get_member(user)
                    member = await config.member(user_obj).events()
                    member_spec = member[event_id]["participating_spec"]
                    spec_emoji = f'{player_class}_{member_spec.replace(" ", "_").lower()}'
                    value_str += f"{spec_emojis[spec_emoji]} {user_obj.mention}\n"
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
                            event_guild.get_member(member).mention
                            for member in signed_up[player_class]
                        ]
                    ),
                )

    # Other statuses

    if len(signed_up.get("bench", [])) > 0 or len(signed_up.get("late", [])) > 0:
        msg = ""
        if len(signed_up.get("bench", [])) > 0:
            msg += (
                f"{button_emojis['bench']} Bench ({len(signed_up['bench'])}): "
                f"{', '.join([event_guild.get_member(member).mention for member in signed_up['bench']])}\n"
            )
        if len(signed_up.get("late", [])) > 0:
            msg += (
                f"{button_emojis['late']} Kasni ({len(signed_up['late'])}): "
                f"{', '.join([event_guild.get_member(member).mention for member in signed_up['late']])}"
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
                f"{button_emojis['tentative']} Neodlučan ({len(signed_up['tentative'])}): "
                f"{', '.join([event_guild.get_member(member).mention for member in signed_up['tentative']])}\n"
            )
        if len(signed_up.get("absent", [])) > 0:
            msg += (
                f"{button_emojis['absent']} Odsutan ({len(signed_up['absent'])}): "
                f"{', '.join([event_guild.get_member(member).mention for member in signed_up['absent']])}"
            )
        embed.add_field(
            name=zws,
            value=msg,
            inline=False,
        )

    return embed
