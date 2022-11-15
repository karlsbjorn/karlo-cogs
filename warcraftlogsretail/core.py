# Most of the source of this file for the actual API mechanics can be found at:
# https://github.com/Kowlin/GraphQL-WoWLogs/blob/master/wowlogs/core.py

import io
import logging
import math
from datetime import datetime
from typing import Literal, Mapping, Optional

import discord
from beautifultable import ALIGN_LEFT, BeautifulTable
from PIL import Image, ImageDraw, ImageFont
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.data_manager import bundled_data_path
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, humanize_list

from .enchantid import ENCHANT_ID
from .encounterid import DIFFICULTIES, ZONES_BY_ID, ZONES_BY_SHORT_NAME
from .http import WoWLogsClient, generate_bearer

_ = Translator("WarcraftLogsRetail", __file__)
log = logging.getLogger("red.karlo-cogs.warcraftlogs")

WCL_URL = "https://www.warcraftlogs.com/reports/{}"


@cog_i18n(_)
class WarcraftLogsRetail(commands.Cog):
    """Retrieve World of Warcraft character information from WarcraftLogs."""

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(
            self, identifier=87446677010550784, force_registration=True
        )
        self.http: WoWLogsClient = None
        self.path = bundled_data_path(self)

        self.config.register_global(bearer_timestamp=0)

        default_user = {
            "charname": None,
            "realm": None,
            "region": None,
        }

        self.config.register_user(**default_user)

    async def _create_client(self) -> None:
        self.http = WoWLogsClient(bearer=await self._get_bearer())
        bearer_status = await self.http.check_bearer()
        if bearer_status is False:
            await generate_bearer(self.bot, self.config)
            await self.http.recreate_session(await self._get_bearer())

    async def _get_bearer(self) -> str:
        api_tokens = await self.bot.get_shared_api_tokens("warcraftlogs")
        bearer = api_tokens.get("bearer", "")

        bearer_timestamp = await self.config.bearer_timestamp()
        timestamp_now = int(datetime.utcnow().timestamp())

        if timestamp_now > bearer_timestamp:
            log.info("Bearer token has expired. Generating one")
            bearer = await generate_bearer(self.bot, self.config)
        elif not bearer:
            log.info("Bearer token doesn't exist. Generating one")
            bearer = await generate_bearer(self.bot, self.config)

        if bearer is None:
            return
        return bearer

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self.http.session.close())

    async def red_get_data_for_user(self, **kwargs):
        return {}

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    @commands.bot_has_permissions(embed_links=True)
    @commands.command()
    async def getgear(
        self, ctx, name: str = None, realm: str = None, *, region: str = None
    ):
        """
        Fetch a character's gear.

        Examples:
        [p]getgear Username Draenor EU
        [p]getgear Username Alterac-Mountains US

        This is provided from the last log entry for a user that includes gear data.
        Not every log has gear data.
        Enchants can be shown - if the log provides them.
        """
        async with ctx.typing():
            userdata = await self.config.user(ctx.author).all()
            if not name:
                name = userdata["charname"]
                if not name:
                    return await ctx.send(
                        _("Please specify a character name with this command.")
                    )
            if not realm:
                realm = userdata["realm"]
                if not realm:
                    return await ctx.send(
                        _("Please specify a realm name with this command.")
                    )
            if not region:
                region = userdata["region"]
                if not region:
                    return await ctx.send(
                        _("Please specify a region name with this command.")
                    )

            if len(region.split(" ")) > 1:
                presplit = region.split(" ")
                realm = f"{realm}-{presplit[0]}"
                region = presplit[1]

            name = name.title()
            realm = realm.title()
            region = region.upper()

            # Get the user's last raid encounters
            encounters = await self.http.get_last_encounter(name, realm, region)

            if encounters is False:
                # the user wasn't found on the API.
                return await ctx.send(
                    _("{name} wasn't found on the API.").format(name=name)
                )

            error = encounters.get("error", None)
            if error:
                return await ctx.send(f"WCL API Error: {error}")

            if encounters is None:
                return await ctx.send(
                    _("The bearer token was invalidated for some reason.")
                )

            char_data = await self.http.get_gear(
                name, realm, region, encounters["latest"]
            )
            if not char_data:
                return await ctx.send(
                    _(
                        "Check your API token and make sure you have added it to the bot correctly."
                    )
                )
            gear = None

            if char_data is None:
                # Assuming bearer has been invalidated.
                await self._create_client()

            if len(char_data["encounterRankings"]["ranks"]) != 0:
                # Ensure this is the encounter that has gear listed. IF its not, we're moving on with the other encounters.
                sorted_by_time = sorted(
                    char_data["encounterRankings"]["ranks"],
                    key=lambda k: k["report"]["startTime"],
                    reverse=True,
                )
                gear = sorted_by_time[0]["gear"]
            else:
                encounters["ids"].remove(encounters["latest"])
                for encounter in encounters["ids"]:
                    char_data = await self.http.get_gear(name, realm, region, encounter)
                    if len(char_data["encounterRankings"]["ranks"]) != 0:
                        sorted_by_time = sorted(
                            char_data["encounterRankings"]["ranks"],
                            key=lambda k: k["report"]["startTime"],
                            reverse=True,
                        )
                        gear = sorted_by_time[0]["gear"]
                        break

            if gear is None:
                return await ctx.send(
                    _("No gear for {name} found in the last report.").format(name=name)
                )

            item_list = []
            item_ilevel = 0
            item_count = 0
            for item in gear:
                if item["id"] == 0:
                    continue
                # item can be {'name': 'Unknown Item', 'quality': 'common', 'id': None, 'icon': 'inv_axe_02.jpg'} here
                rarity = self._get_rarity(item)
                item_ilevel_entry = item.get("itemLevel", None)
                if item_ilevel_entry:
                    if int(item["itemLevel"]) > 5:
                        item_ilevel += int(item["itemLevel"])
                        item_count += 1
                item_list.append(
                    f"{rarity} [{item['name']}](https://wowhead.com/item={item['id']})"
                )
                perm_enchant_id = item.get("permanentEnchant", None)
                temp_enchant_id = item.get("temporaryEnchant", None)
                gem_id = item.get("gems", None)
                gem_id = gem_id[0].get("id", None) if gem_id else None
                perm_enchant_text = ENCHANT_ID.get(perm_enchant_id, None)
                temp_enchant_text = ENCHANT_ID.get(temp_enchant_id, None)
                gem_text = ENCHANT_ID.get(gem_id, None)
                # TODO: Add sockets and socketed gems to the embed.

                if perm_enchant_id:
                    if temp_enchant_id:
                        symbol = "├"
                    elif gem_id:
                        symbol = "├"
                    else:
                        symbol = "└"
                    if perm_enchant_text:
                        item_list.append(f"`{symbol}──` {perm_enchant_text}")
                    if gem_text:
                        item_list.append(f"`{symbol}──` {gem_text}")
                if gem_id:
                    if temp_enchant_id:
                        symbol = "├"
                    else:
                        symbol = "└"
                    if gem_text:
                        item_list.append(f"`{symbol}──` {gem_text}")
                if temp_enchant_id:
                    if temp_enchant_text:
                        item_list.append(f"`└──` {temp_enchant_text}")

            if item_ilevel > 0:
                avg_ilevel = "{:g}".format(item_ilevel / item_count)
            else:
                avg_ilevel = _("Unknown (not present in log data from the API)")

            # embed
            embed = discord.Embed()
            title = f"{name.title()} - {realm.title()} ({region.upper()})"
            guild_name = sorted_by_time[0]["guild"].get("name", None)
            if guild_name:
                title += f"\n{guild_name}"
            embed.title = title
            embed.description = "\n".join(item_list)
            embed.colour = await ctx.embed_color()

            # embed footer
            ilvl = _("Average Item Level: {avg_ilevel}\n").format(avg_ilevel=avg_ilevel)
            encounter_spec = sorted_by_time[0].get("spec", None)
            spec = _("Encounter spec: {encounter_spec}\n").format(
                encounter_spec=encounter_spec
            )
            gear_data = _("Gear data pulled from {report_url}\n").format(
                report_url=WCL_URL.format(sorted_by_time[0]["report"]["code"])
            )
            log_date = _("Log Date/Time: {datetime} UTC").format(
                datetime=self._time_convert(sorted_by_time[0]["startTime"])
            )
            embed.set_footer(text=f"{spec}{ilvl}{gear_data}{log_date}")

            await ctx.send(embed=embed)

    @commands.bot_has_permissions(embed_links=True)
    @commands.command()
    async def getrank(
        self,
        ctx,
        name: str = None,
        realm: str = None,
        region: str = None,
        zone: str = None,
        difficulty: str = None,
    ):
        """
        Character rank overview.

        If the realm name is two words, use a hyphen to connect the words.

        Examples:
        [p]getrank Username Draenor EU
        [p]getrank Username Alterac-Mountains US

        Specific Zones:
        [p]getrank Username Draenor EU CN Heroic
        [p]getrank Username Alterac-Mountains US SoD Mythic

        Zone name must be formatted like:
        CN, SoD, SotFO
        """
        # someone has their data saved so they are just trying
        # to look up a zone for themselves
        async with ctx.typing():
            if name:
                if name.upper() in ZONES_BY_SHORT_NAME:
                    zone = name
                    name = None
                    realm = None
                    region = None

            # look up any saved info
            userdata = await self.config.user(ctx.author).all()
            if not name:
                name = userdata["charname"]
                if not name:
                    return await ctx.send(
                        _("Please specify a character name with this command.")
                    )
            if not realm:
                realm = userdata["realm"]
                if not realm:
                    return await ctx.send(
                        _("Please specify a realm name with this command.")
                    )
            if not region:
                region = userdata["region"]
                if not region:
                    return await ctx.send(
                        _("Please specify a region name with this command.")
                    )

            region = region.upper()
            if region not in ["US", "EU"]:
                msg = _(
                    "Realm names that have a space (like 'Nethergarde Keep') must be written with a hyphen, "
                )
                msg += _(
                    "upper or lower case: `nethergarde-keep` or `Nethergarde-Keep`."
                )
                return await ctx.send(msg)

            name = name.title()
            realm = realm.title()

            # fetch zone name and zone id from user input
            zone_id = None
            if zone:
                if zone.upper() in ZONES_BY_SHORT_NAME:
                    zone_id = ZONES_BY_SHORT_NAME[zone.upper()][1]
                    zone_id_to_name = ZONES_BY_SHORT_NAME[zone.upper()][0]
            if difficulty and difficulty.upper() in DIFFICULTIES.values():
                difficulty_ids = list(DIFFICULTIES.keys())
                for difficulty_id in difficulty_ids:
                    if difficulty.upper() == DIFFICULTIES[difficulty_id]:
                        difficulty = difficulty_id
                        break
            else:
                difficulty = 0

            if zone_id is None:
                # return first raid that actually has parse info in shadowlands
                # as no specific zone was requested
                zone_ids = list(ZONES_BY_ID.keys())
                zone_ids.reverse()
                for zone_number in zone_ids:
                    data = await self.http.get_overview(
                        name, realm, region, zone_number, difficulty
                    )
                    error = data.get("error", None)
                    if error:
                        return await ctx.send(f"WCL API Error: {error}")
                    if (data is False) or (
                        not data["data"]["characterData"]["character"]
                    ):
                        return await ctx.send(
                            _("{name} wasn't found on the API.").format(name=name)
                        )
                    char_data = data["data"]["characterData"]["character"][
                        "zoneRankings"
                    ]
                    data_test = char_data.get("bestPerformanceAverage", None)
                    if data_test is not None:
                        break
            else:
                # try getting a specific zone's worth of info for this character
                data = await self.http.get_overview(
                    name, realm, region, zone_id, difficulty
                )
                error = data.get("error", None)
                if error:
                    return await ctx.send(f"WCL API Error: {error}")
                if (data is False) or (not data["data"]["characterData"]["character"]):
                    return await ctx.send(
                        _("{name} wasn't found on the API.").format(name=name)
                    )

            # embed and data setup
            zws = "\N{ZERO WIDTH SPACE}"
            space = "\N{SPACE}"

            try:
                char_data = data["data"]["characterData"]["character"]["zoneRankings"]
            except (KeyError, TypeError):
                msg = _(
                    "Something went terribly wrong while trying to access the zone rankings for this character."
                )
                return await ctx.send(msg)

            try:
                difficulty = (
                    await self._difficulty_name_from_id(char_data["difficulty"])
                ).capitalize()
            except KeyError:
                await ctx.send("No data found for that difficulty.")
                return
            zone_name = await self._zone_name_from_id(char_data["zone"])
            zone_name = f"⫷ {difficulty} {zone_name} ⫸".center(40, " ")

            embed = discord.Embed()
            embed.title = f"{name.title()} - {realm.title()} ({region.upper()})"
            embed.colour = await ctx.embed_color()

            # perf averages
            embed.add_field(name=zws, value=box(zone_name, lang="fix"), inline=False)

            perf_avg = char_data.get("bestPerformanceAverage", None)
            if perf_avg:
                pf_avg = "{:.1f}".format(char_data["bestPerformanceAverage"])
                pf_avg = self._get_color(float(pf_avg))
                embed.add_field(name=_("Best Perf. Avg"), value=pf_avg, inline=True)
            else:
                if zone_id:
                    return await ctx.send(
                        _(
                            "Nothing found for {zone_name} for this player for Shadowlands."
                        ).format(zone_name=zone_id_to_name.title())
                    )
                else:
                    return await ctx.send(
                        _("Nothing at all found for this player for Shadowlands.")
                    )

            md_avg = "{:.1f}".format(char_data["medianPerformanceAverage"])
            md_avg = self._get_color(float(md_avg))
            embed.add_field(name=_("Median Perf. Avg"), value=md_avg, inline=True)

            # perf avg filler space
            embed.add_field(name=zws, value=zws, inline=True)

            # table setup
            table = BeautifulTable(default_alignment=ALIGN_LEFT, maxwidth=500)
            table.set_style(BeautifulTable.STYLE_COMPACT)
            table.columns.header = [
                _("Name"),
                _("Best %"),
                _("Spec"),
                _("DPS"),
                _("Kills"),
                _("Fastest"),
                _("Med %"),
                _("AS Pts"),
                _("AS Rank"),
            ]

            # add rankings per encounter to table
            rankings = char_data["rankings"]
            for encounter in rankings:
                all_stars = encounter["allStars"]
                enc_details = encounter["encounter"]
                best_amt = (
                    "{:.1f}".format(encounter["bestAmount"])
                    if encounter["bestAmount"] != 0
                    else "-"
                )
                median_pct = (
                    "{:.1f}".format(encounter["medianPercent"])
                    if encounter["medianPercent"]
                    else "-"
                )
                rank_pct = (
                    "{:.1f}".format(encounter["rankPercent"])
                    if encounter["medianPercent"]
                    else "-"
                )
                fastest_kill_tup = self._dynamic_time(encounter["fastestKill"] / 1000)

                if fastest_kill_tup == (0, 0):
                    fastest_kill = "-"
                else:
                    if len(str(fastest_kill_tup[1])) == 1:
                        seconds = f"0{fastest_kill_tup[1]}"
                    else:
                        seconds = fastest_kill_tup[1]
                    fastest_kill = f"{fastest_kill_tup[0]}:{seconds}"

                table.rows.append(
                    (
                        enc_details.get("name", None),
                        rank_pct,
                        encounter["spec"],
                        best_amt,
                        encounter["totalKills"],
                        fastest_kill,
                        median_pct,
                        all_stars.get("points", None) if all_stars else "-",
                        all_stars.get("rank", None) if all_stars else "-",
                    )
                )

            # all stars
            all_stars = char_data["allStars"]
            section_name = _("⫷ Expansion All Stars ⫸").center(40, " ")
            embed.add_field(
                name=zws, value=box(section_name, lang="Prolog"), inline=False
            )
            for item in all_stars:
                msg = f"**{item['spec']}**\n"
                rank_percent = "{:.1f}".format(item["rankPercent"])
                msg += _("Points:\n`{points}`\n").format(points=item["points"])
                msg += _("Rank:\n`{rank}`\n").format(rank=item["rank"])
                msg += f"{self._get_color(float(rank_percent), '%')}\n"
                embed.add_field(name=zws, value=msg, inline=True)

            # all stars filler space
            if not len(all_stars) % 3 == 0:
                nearest_multiple = 3 * math.ceil(len(all_stars) / 3)
            else:
                nearest_multiple = len(all_stars)
            bonus_empty_fields = nearest_multiple - len(all_stars)
            if bonus_empty_fields > 0:
                for _1 in range(bonus_empty_fields):
                    embed.add_field(name=zws, value=zws, inline=True)

            # table time
            table_image = await self._make_table_image(str(table))
            image_file = discord.File(fp=table_image, filename="table_image.png")
            embed.set_image(url=f"attachment://{image_file.filename}")

            await ctx.send(file=image_file, embed=embed)

    @commands.command()
    async def wclcharname(self, ctx, charname: str):
        """Set your character's name."""
        await self.config.user(ctx.author).charname.set(charname)
        await ctx.send(
            _("Your character name was set to {charname}.").format(
                charname=charname.title()
            )
        )

    @commands.command()
    async def wclrealm(self, ctx, *, realm: str):
        """Set your realm."""
        realmname = realm.replace(" ", "-")
        await self.config.user(ctx.author).realm.set(realmname)
        await ctx.send(_("Your realm was set to {realm}.").format(realm=realm.title()))

    @commands.command()
    async def wclregion(self, ctx, region: str):
        """Set your region."""
        valid_regions = ["EU", "US"]
        if region.upper() not in valid_regions:
            return await ctx.send(
                _("Valid regions are: {valid_regions}").format(
                    valid_regions=humanize_list(valid_regions)
                )
            )
        await self.config.user(ctx.author).region.set(region)
        await ctx.send(
            _("Your realm's region was set to {region}.").format(region=region.upper())
        )

    @commands.command()
    async def wclsettings(self, ctx, user: discord.User = None):
        """Show your current settings."""
        if not user:
            user = ctx.author
        userinfo = await self.config.user(user).all()
        msg = _("[Settings for {user}]\n").format(user=user.display_name)
        charname = userinfo["charname"].title() if userinfo["charname"] else "None"
        realmname = (
            userinfo["realm"].title().replace("-", " ") if userinfo["realm"] else "None"
        )
        regionname = userinfo["region"].upper() if userinfo["region"] else "None"
        msg += _(
            "Character: {charname}\nRealm: {realmname}\nRegion: {regionname}\n\n"
        ).format(charname=charname, realmname=realmname, regionname=regionname)

        msg += _("[Bot Permissions Needed]\n")
        if ctx.message.guild.me.guild_permissions.embed_links:
            msg += _("[X] Embed Links permissions\n")
        else:
            msg += _("[ ] I need Embed Links permissions\n")

        await ctx.send(box(msg, lang="ini"))

    @commands.command()
    @checks.is_owner()
    async def wclapikey(self, ctx):
        """Instructions for setting the api key."""
        msg = "Set your API key by adding it to Red's API key storage.\n"
        msg += "Get a key from <https://www.warcraftlogs.com> by signing up for an account, then visit your settings.\n"
        msg += "At the bottom is a section called Web API. Click on the blue link that says `manage your V2 clients here`.\n"
        msg += "Do NOT sign up for a v1 API key, it will not work with this cog.\n"
        msg += "Click on Create Client. Be ready to write down your information somewhere, you cannot retrive the secret after this.\n"
        msg += "Enter a name (whatever you want), `https://localhost` for the redirect URL, and leave the Public Client box unchecked.\n"
        msg += f"Use `{ctx.prefix}set api warcraftlogs client_id,client-id-goes-here client_secret,client-secret-goes-here` to set your key.\n"
        await ctx.send(msg)

    @commands.command(hidden=True)
    @checks.is_owner()
    async def wclrank(self, ctx):
        """[Depreciated] Fetch ranking info about a player."""
        msg = "This cog has changed significantly from the last update.\n"
        msg += f"Use `{ctx.prefix}help WarcraftLogsRetail` to see all commands.\n"
        msg += f"Use `{ctx.prefix}wclapikey` to see instructions on how to get the new API key.\n"
        await ctx.send(msg)

    @commands.command(hidden=True)
    @commands.guild_only()
    async def wclgear(self, ctx):
        """[Depreciated] Fetch gear info about a player."""
        msg = "This cog has changed significantly from the last update.\n"
        msg += f"Use `{ctx.prefix}help WarcraftLogsRetail` to see all commands.\n"
        msg += f"Use `{ctx.prefix}wclapikey` to see instructions on how to get the new API key.\n"
        await ctx.send(msg)

    async def _make_table_image(self, table):
        image_path = str(self.path / "blank.png")
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(str(self.path / "Cousine-Regular.ttf"), 20)

        x = 20
        y = 0

        text_lines = table.split("\n")
        for text_line in text_lines:
            y += 25
            draw.text((x, y), text_line, font=font, fill=(255, 255, 255, 255))

        image_object = io.BytesIO()
        image.save(image_object, format="PNG")
        image_object.seek(0)
        return image_object

    @staticmethod
    def _dynamic_time(time_elapsed):
        m, s = divmod(int(time_elapsed), 60)
        return m, s

    @staticmethod
    def _get_rarity(item):
        rarity = item["quality"]
        if rarity == "common":
            return "⬜"
        elif rarity == "uncommon":
            return "🟩"
        elif rarity == "rare":
            return "🟦"
        elif rarity == "epic":
            return "🟪"
        elif rarity == "legendary":
            return "🟧"
        else:
            return "🔳"

    @staticmethod
    def _time_convert(time):
        time = str(time)[0:10]
        value = datetime.fromtimestamp(int(time)).strftime("%Y-%m-%d %H:%M:%S")
        return value

    @staticmethod
    async def _zone_name_from_id(zoneid: int) -> str:
        for zone_id, zone_name in ZONES_BY_ID.items():
            if zoneid == zone_id:
                return zone_name

    @staticmethod
    async def _difficulty_name_from_id(difficultyid: int) -> str:
        for difficulty_id, difficulty_name in DIFFICULTIES.items():
            if difficultyid == difficulty_id:
                return difficulty_name

    def _get_color(self, number: float, bonus=""):
        if number >= 95:
            # legendary
            out = self._orange(number, bonus)
        elif 94 >= number > 75:
            # epic
            out = self._red(number, bonus)
        elif 75 >= number > 50:
            # rare
            out = self._blue(number, bonus)
        elif 50 >= number > 25:
            # common
            out = self._green(number, bonus)
        elif 25 >= number >= 0:
            # trash
            out = self._grey(number, bonus)
        else:
            # someone fucked up somewhere
            out = box(str(number))
        return out

    @staticmethod
    def _red(number, bonus):
        output_center = f"{str(number)}{bonus}".center(8, " ")
        text = f" [  {output_center}  ]"
        new_number = f"{box(text, lang='css')}"
        return new_number

    @staticmethod
    def _orange(number, bonus):
        output_center = f"{str(number)}{bonus}".center(8, " ")
        text = f" [  {output_center}  ]"
        new_number = f"{box(text, lang='fix')}"
        return new_number

    @staticmethod
    def _green(number, bonus):
        output_center = f"{str(number)}{bonus}".center(8, " ")
        text = f" [  {output_center}  ]"
        new_number = f"{box(text, lang='py')}"
        return new_number

    @staticmethod
    def _blue(number, bonus):
        output_center = f"{str(number)}{bonus}".center(8, " ")
        text = f" [  {output_center}  ]"
        new_number = f"{box(text, lang='ini')}"
        return new_number

    @staticmethod
    def _grey(number, bonus):
        output_center = f"{str(number)}{bonus}".center(8, " ")
        text = f" [  {output_center}  ]"
        new_number = f"{box(text, lang='bf')}"
        return new_number

    @commands.Cog.listener()
    async def on_red_api_tokens_update(
        self, service_name: str, api_tokens: Mapping[str, str]
    ):
        """Lifted shamelessly from GHC. Thanks Kowlin for this and everything else you did on this cog."""
        if service_name != "warcraftlogs":
            return
        await self.http.recreate_session(await self._get_token(api_tokens))

    async def _get_token(self, api_tokens: Optional[Mapping[str, str]] = None) -> str:
        """Get WCL bearer token."""
        if api_tokens is None:
            api_tokens = await self.bot.get_shared_api_tokens("warcraftlogs")

        bearer = api_tokens.get("bearer", None)
        if not bearer:
            log.info("No valid token found, trying to create one.")
            await generate_bearer(self.bot, self.config)
            return await self._get_bearer()
        else:
            return bearer
