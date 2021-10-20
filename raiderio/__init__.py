from .raiderio import Raiderio


def setup(bot):
    bot.add_cog(Raiderio(bot))
