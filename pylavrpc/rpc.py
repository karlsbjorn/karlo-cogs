from pylav.players.player import Player
from pylav.players.query.obj import Query


class RPC:
    async def get_current_track(self, guild_id: int):
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

    async def play_track(self, guild_id: int, query: str):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return {"status": 404, "message": "Guild not found."}

        player: Player = self.bot.lavalink.get_player(guild_id)
        if not player:
            return {"status": 400, "message": "Bot not connected to voice channel."}

        query = await Query.from_string(query)
        response = await self.bot.lavalink.search_query(query=query)
        if response.loadType == "error":
            return {"status": 400, "message": "Error getting track"}

        await player.play(query=query, track=response.data, requester=guild.me)
        return {
            "status": 200,
            "message": "Track playing successfully",
            "track": await player.current.to_dict(),
        }

    async def play_next(self, guild_id: int):
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
