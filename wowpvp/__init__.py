from .wowpvp import Wowpvp


def setup(bot):
    bot.add_cog(Wowpvp(bot))
