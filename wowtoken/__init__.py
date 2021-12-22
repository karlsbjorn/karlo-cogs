from .wowtoken import Wowtoken


def setup(bot):
    bot.add_cog(Wowtoken(bot))
