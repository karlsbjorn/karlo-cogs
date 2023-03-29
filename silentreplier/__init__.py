"""
A large majority of the code here is from Zephyrkul's cmdreplier
https://github.com/Zephyrkul/FluffyCogs/blob/master/cmdreplier/__init__.py
Thanks Zeph
"""

import contextlib
from functools import partial

from redbot.core import commands
from redbot.core.bot import Red


async def silent_send(__sender, /, *args, **kwargs):
    ctx: commands.Context = __sender.__self__
    if not ctx.command_failed and "silent" not in kwargs:
        kwargs["silent"] = True
    return await __sender(*args, **kwargs)


async def before_hook(ctx: commands.Context):
    if not ctx.message.edited_at and ctx.message.flags.silent:
        with contextlib.suppress(AttributeError):
            del ctx.send
        ctx.send = partial(silent_send, ctx.send)


async def setup(bot: Red):
    bot.before_invoke(before_hook)


async def teardown(bot: Red):
    bot.remove_before_invoke_hook(before_hook)
