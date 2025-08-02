from piccolo.columns import BigInt, ForeignKey, Integer, SmallInt, Text, Varchar
from piccolo.engine import PostgresEngine
from piccolo.table import Table

from .config import DB_CONFIG

DB = PostgresEngine(config=DB_CONFIG)


# Every table here needs to be the same as the one in konjanik-auth/models.py


class DiscordToken(Table, db=DB):
    user_id = BigInt(primary_key=True, unique=True)
    access_token = Text(null=True)
    refresh_token = Text(null=True)
    expires_at = BigInt(null=True)


class BnetToken(Table, db=DB):
    user_id = BigInt(primary_key=True, unique=True)
    access_token = Text(null=True)
    token_type = Varchar(length=50, null=True)
    expires_at = BigInt(null=True)
    scope = Text(null=True)
    sub = Text(null=True)  # bnet id


class GuildMember(Table, db=DB):
    user_id = BigInt(primary_key=True, unique=True)
    discord_token: ForeignKey[DiscordToken] = ForeignKey(references=DiscordToken)
    bnet_token = ForeignKey(references=BnetToken)
    guild_rank = Text(null=True)
    guild_lb_position = SmallInt(null=True)
    main_character_id = Integer(null=True)


class Character(Table, db=DB):
    character_id = BigInt(primary_key=True, unique=True)
    character_name = Varchar(length=100)
    realm_id = BigInt()
    realm = Varchar(length=100)
    guild = Varchar(length=100, null=True)
    bnet_token = ForeignKey(references=BnetToken)
    ilvl = Text(null=True)
    score = Text(null=True)
    guild_member = ForeignKey(references=GuildMember)
