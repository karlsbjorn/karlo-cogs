from .wowtools import WoWTools


def setup(bot):
    bot.add_cog(WoWTools(bot))
