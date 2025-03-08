from typing import List

import discord
from discord.app_commands import AppCommandContext, AppInstallationType
from raiderio_async import RaiderIO
from redbot.core import app_commands
from redbot.core.commands import Context
from redbot.core.i18n import Translator
from wowtools.raiderio import ProfileMenu, Raiderio
from wowtools.utils import get_realms

_ = Translator("WoWTools", __file__)


class UserInstallableRaiderio:
    user_install_raiderio = app_commands.Group(
        name="raiderio",
        description=_("Raider.io commands"),
        allowed_installs=AppInstallationType(guild=True, user=True),
        allowed_contexts=AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    )

    @user_install_raiderio.command(name="profile")
    @app_commands.describe(
        character="Name of the character to look up",
        realm="The character's realm",
    )
    async def user_install_raiderio_profile(
        self, interaction: discord.Interaction, character: str, realm: str
    ) -> None:
        """Display the raider.io profile of a character.

        **Example:**
        [p]raiderio profile Karlo Ragnaros
        """
        realm, region = realm.split(sep=":")
        realm = ("-".join(realm).lower() if isinstance(realm, tuple) else realm.lower()).replace(
            " ", "-"
        )
        region = region.lower()
        await interaction.response.defer()
        async with RaiderIO() as rio:
            profile_data = await rio.get_character_profile(
                region,
                realm,
                character,
                fields=[
                    "mythic_plus_scores_by_season:current",
                    "raid_progression",
                    "gear",
                    "mythic_plus_best_runs",
                    "talents",
                    "guild",
                ],
            )

        try:
            char_name = profile_data["name"]
        except KeyError:
            await interaction.followup.send(_("Character not found."))
            return
        char_race = profile_data["race"]
        char_spec = profile_data["active_spec_name"]
        char_class = profile_data["class"]
        char_guild = profile_data["guild"]["name"]
        char_image = profile_data["thumbnail_url"]
        char_score = profile_data["mythic_plus_scores_by_season"][0]["segments"]["all"]
        char_score_color = int("0x" + char_score["color"][1:], 0)
        char_raid = profile_data["raid_progression"]["liberation-of-undermine"]["summary"]
        char_last_updated = Raiderio.parse_date(profile_data["last_crawled_at"])
        char_gear = profile_data["gear"]
        char_ilvl = char_gear["item_level_equipped"]
        char_url = profile_data["profile_url"]
        char_talents = profile_data["talentLoadout"]["loadout_text"]

        banner = profile_data["profile_banner"]

        banner_url = (
            f"https://cdnassets.raider.io/images/profile/masthead_backdrops/v2/{banner}.jpg"
        )
        armory_url = f"https://worldofwarcraft.com/en-gb/character/{region}/{realm}/{char_name}"
        wcl_url = f"https://www.warcraftlogs.com/character/{region}/{realm}/{char_name}"
        raidbots_url = (
            f"https://www.raidbots.com/simbot/quick?region={region}&realm={realm}&name={char_name}"
        )

        # First page
        embed = discord.Embed(
            title=char_name,
            url=char_url,
            description=f"{char_race} {char_spec} {char_class}\n<{char_guild}>",
            color=char_score_color,
        )
        embed.set_author(
            name=_("Raider.io profile"),
            icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg",
        )
        embed.set_thumbnail(url=char_image)
        embed.add_field(
            name=_("__**Mythic+ Score**__"),
            value=char_score["score"],
            inline=False,
        )
        embed.add_field(name=_("Raid progress"), value=char_raid, inline=True)
        embed.add_field(name=_("Item level"), value=char_ilvl, inline=True)
        embed.add_field(
            name=_("__Other links__"),
            value=_(
                "[Armory]({armory_url}) | [WarcraftLogs]({wcl_url}) | [Raidbots]({raidbots_url})"
            ).format(
                armory_url=armory_url,
                wcl_url=wcl_url,
                raidbots_url=raidbots_url,
            ),
            inline=False,
        )
        embed.set_image(url=banner_url)
        embed.set_footer(
            text=_("Last updated: {char_last_updated}").format(char_last_updated=char_last_updated)
        )
        embeds = [embed]

        # As of TWW, fortified and tyrannical no longer track separately
        #
        # if runs := Raiderio.get_all_runs(profile_data):
        #     data = [
        #         [dungeon, runs["Fortified"], runs["Tyrannical"]] for dungeon, runs in runs.items()
        #     ]
        #     tabulated = tabulate(
        #         data,
        #         headers=[_("Dungeon"), _("Forti"), _("Tyrann")],
        #         tablefmt="simple",
        #         colalign=("left", "right", "right"),
        #     )

        #     embed = discord.Embed(
        #         title=char_name,
        #         description=box(
        #             tabulated,
        #         ),
        #         url=char_url,
        #         color=char_score_color,
        #     )
        #     embed.set_author(
        #         name=_("Raider.io profile"),
        #         icon_url="https://cdnassets.raider.io/images/fb_app_image.jpg",
        #     )
        #     embed.set_thumbnail(url=char_image)
        #     embed.set_footer(
        #         text=_("Last updated: {char_last_updated}").format(
        #             char_last_updated=char_last_updated
        #         )
        #     )
        #     embeds.append(embed)

        # Gear page
        embed = await Raiderio.make_gear_embed(
            char_gear, char_image, char_last_updated, char_name, char_score_color, char_url
        )
        embeds.append(embed)

        ctx: Context = await Context.from_interaction(interaction)
        await ProfileMenu(pages=embeds, talents=char_talents, disable_after_timeout=True).start(
            ctx
        )

    @user_install_raiderio_profile.autocomplete("realm")
    async def raiderio_profile_realm_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        realms = await get_realms(current)
        return realms[:25]
