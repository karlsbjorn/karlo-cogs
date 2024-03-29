from .pylavrpc import PyLavRPC


async def setup(bot):
    await bot.add_cog(PyLavRPC(bot))
