from typing import Any

import discord
from discord.ext import commands
import reddit
import apraw
import aiofiles


class Momnisaur(commands.Bot):
    def __init__(self, *, intents: discord.Intents, **options: Any):
        super().__init__(intents=intents, **options)

    async def sync_commands(self):
        await self.tree.sync(guild=self.get_guild(518833007398748161))

    async def on_ready(self):
        print(f'We have logged in as {self.user}')
        await reddit.setup(self, self.get_guild(518833007398748161))

    async def on_message(self, message):
        if message.author == self.user:
            return

        if "<@983043389425610873>" in message.content and "👋" in message.content:
            await message.channel.send(':wave:')
        elif "<@983043389425610873>" in message.content and "sync" in message.content:
            if self.get_guild(518833007398748161).get_role(525501383189856278) not in message.author.roles:
                await message.channel.send("You're not an admin <:nomno:771467601229774859>")
                return

            await message.channel.send('Syncing slash commands <:nomrawr:771467600953212959>')
            await self.sync_commands()
        else:
            await super().on_message(message)
