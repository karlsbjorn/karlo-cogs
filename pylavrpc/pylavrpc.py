from pylav.type_hints.bot import DISCORD_BOT_TYPE
from redbot.core import commands

from pylavrpc.rpc import RPC


class PyLavRPC(RPC, commands.Cog):
    def __init__(self, bot):
        self.bot: DISCORD_BOT_TYPE = bot
        self.bot.register_rpc_handler(self.get_current_track)
        self.bot.register_rpc_handler(self.play_track)
        self.bot.register_rpc_handler(self.play_next)

    def cog_unload(self):
        self.bot.unregister_rpc_handler(self.get_current_track)
        self.bot.unregister_rpc_handler(self.play_track)
        self.bot.unregister_rpc_handler(self.play_next)
