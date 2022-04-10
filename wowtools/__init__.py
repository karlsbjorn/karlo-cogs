from .wowtools import WoWTools


async def setup(bot):
    await bot.add_cog(WoWTools(bot))
