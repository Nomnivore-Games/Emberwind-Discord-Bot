import os
import logging

from dotenv import load_dotenv
from interactions import Client, Intents, listen

load_dotenv()
DISCORD_KEY = os.getenv("DISCORD_KEY")

logging.basicConfig()
cls_log = logging.getLogger(__name__)
cls_log.setLevel(logging.DEBUG)

bot = Client(
    intents=Intents.DEFAULT & ~Intents.DIRECT_MESSAGES | Intents.MESSAGE_CONTENT | Intents.GUILD_MEMBERS,
    sync_interactions=True,
    asyncio_debug=True,
    logger=cls_log,
    activity="EMBERWIND",
    delete_unused_application_cmds=True,
)


@listen()
async def on_ready():
    print("Ready")
    print(f"This bot is owned by {bot.owner}")


bot.load_extension("interactions.ext.jurigged")
bot.load_extension("momnisaur.extensions.AI")
bot.start(DISCORD_KEY)
