import json
from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands


@dataclass
class RedditInfo:
    post_channel: discord.TextChannel
    followed_reddits: list[str]
    reddits_to_search: list[str]
    keyword_weights: dict[str, int]

    def to_json(self):
        return {
            "post_channel": self.post_channel.id,
            "followed_reddits": self.followed_reddits,
            "reddits_to_search": self.reddits_to_search,
            "keyword_weights": self.keyword_weights,
        }

    @staticmethod
    def from_json(bot: commands.Bot, reddit_json: dict):
        return RedditInfo(
            post_channel=bot.get_channel(reddit_json["post_channel"]),
            followed_reddits=reddit_json["followed_reddits"],
            reddits_to_search=reddit_json["reddits_to_search"],
            keyword_weights=reddit_json["keyword_weights"],
        )


class RedditCog(commands.GroupCog, name="reddit"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="set-channel")
    @commands.has_guild_permissions(manage_webhooks=True)
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(f"Reddit posts will now be posted in #{channel.name}", ephemeral=True)
        print(channel)

    @app_commands.command(name="add-sub")
    @commands.has_guild_permissions(manage_webhooks=True)
    async def add_sub(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Hello from sub command 1", ephemeral=True)
        reddit_info = RedditInfo(
            post_channel=self.bot.get_guild(518833007398748161).get_channel(985381944126734397),
            followed_reddits=[],
            reddits_to_search=[],
            keyword_weights={},
        )
        print(json.dumps(reddit_info.to_json()))
        reddit_info_two = RedditInfo.from_json(self.bot, json.loads(json.dumps(reddit_info.to_json())))
        print(json.dumps(reddit_info_two.to_json()))


async def setup(bot: commands.Bot, guild: discord.Guild) -> None:
    await bot.add_cog(RedditCog(bot), guild=guild)
