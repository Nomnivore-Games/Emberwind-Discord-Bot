import asyncpraw

from interactions import slash_command, slash_option, SlashContext, Extension, OptionType, Client, Embed, listen


class Reddit(Extension):
    def __init__(self, bot):
        self._last_member = None

        self.client_id = ""
        self.client_secret = ""
        self.user_agent = "prawthing1"
        self.reddit = asyncpraw.Reddit(
            client_id = self.client_id,
            client_secret = self.client_secret,
            user_agent = self.user_agent
        )

    @listen()
    async def on_ready(self):
        print("Reddit loaded")
        channel = self.bot.get_channel(1042831507154292816)
        subreddit = await self.reddit.subreddit('all')
        urlstart = "http://www.reddit.com/"
        async for submissions in subreddit.stream.submissions():
            try:
                await channel.send(urlstart+submissions.permalink)
            except Exception as e:
                pass


def setup(bot):
    Reddit(bot)
