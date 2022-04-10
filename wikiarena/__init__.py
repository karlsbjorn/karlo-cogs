from .wikiarena import WikiArena


async def setup(bot):
    await bot.add_cog(WikiArena(bot))
