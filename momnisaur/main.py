import os

from dotenv import load_dotenv
import discord
import momnisaur

load_dotenv()
TOKEN = os.getenv("TOKEN")


def main():
    intents = discord.Intents.default()
    intents.message_content = True
    activity = discord.Activity(name="EMBERWIND", type=discord.ActivityType.playing)
    mom = momnisaur.Momnisaur(intents=intents, activity=activity, command_prefix="$")
    mom.run(TOKEN)


if __name__ == "__main__":
    main()
