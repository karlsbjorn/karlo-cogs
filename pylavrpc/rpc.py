from typing import Any


import discord
from pylav.players.player import Player
from pylav.players.query.obj import Query


class RPC:
    async def get_current_track(self, guild_id: int) -> dict[str, Any]:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return {"status": 404, "message": "Guild not found."}

        player: Player = self.bot.lavalink.get_player(guild_id)
        if not player:
            return {"status": 400, "message": "Bot not connected to voice channel."}

        current_track = player.current
        if not current_track:
            return {"status": 400, "message": "Bot not playing anything."}

        return await current_track.to_dict()

    async def play_track(self, guild_id: int, query: str) -> dict[str, Any]:
        if not query:
            return {"status": 400, "message": "No query provided."}

        guild: discord.Guild = self.bot.get_guild(guild_id)  # type: ignore
        if not guild:
            return {"status": 404, "message": "Guild not found."}

        player: Player = self.bot.lavalink.get_player(guild_id)
        if not player:
            return {"status": 400, "message": "Bot not connected to voice channel."}

        query_obj: Query = await Query.from_string(query)
        if query_obj.is_album or query_obj.is_playlist:
            return {"status": 400, "message": "Only single tracks allowed on this endpoint."}
        response = await self.bot.lavalink.search_query(query=query_obj)
        if response.loadType == "error":
            return {"status": 400, "message": "Error getting track"}

        await player.play(query=query, track=response.data, requester=guild.me)
        if player.current:
            return {
                "status": 200,
                "message": "Track playing successfully",
                "track": await player.current.to_dict(),
            }
        return {"status": 400, "message": "Error playing track."}

    async def play_next(self, guild_id: int) -> dict[str, Any]:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return {"status": 404, "message": "Guild not found."}

        player: Player = self.bot.lavalink.get_player(guild_id)
        if not player:
            return {"status": 400, "message": "Bot not connected to voice channel."}

        current_track = player.current
        if not current_track:
            return {"status": 400, "message": "Bot not playing anything."}

        if not player.next_track:
            return {"status": 400, "message": "No next track in queue"}

        await player.next()
        return {
            "status": 200,
            "message": "Next track started playing successfully.",
            "track": await player.current.to_dict(),
        }
