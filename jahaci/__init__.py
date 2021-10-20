from .jahaci import Jahaci


def setup(bot):
    bot.add_cog(Jahaci(bot))
