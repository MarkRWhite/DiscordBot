import discord
from discord.ext import commands
import argparse
import logging
import signal
import sys
import os
import dotenv

class Bot:
    def cleanup(self, signum, frame):
        # Perform cleanup operations here
        print("Bot is cleaning up...")
        # Create a task to close the bot
        self.bot.loop.create_task(self.bot.close())
        sys.exit(0)

    def __init__(self, token_env_var, log_file):
        signal.signal(signal.SIGINT, self.cleanup) # Set up cleanup signal handler so we can close the process gracefully
        dotenv.load_dotenv()  # Load environment variables from .env file

        if not token_env_var:
            raise ValueError("token_env_var argument is required.")
        self.TOKEN = os.getenv(token_env_var)
        if not self.TOKEN:
            raise ValueError(f"Environment variable {token_env_var} is not set.")

        self.log_file = log_file
        if not self.log_file:
            raise ValueError("log_file argument is required.")

        self.bot = commands.Bot(command_prefix='!')
        self.bot.add_listener(self.on_ready)
        self.bot.add_command(self.hello)

    async def on_ready(self):
        print(f'We have logged in as {self.bot.user}')

    @commands.command()
    async def hello(self, ctx):
        await ctx.send('Hello!')

    def run(self):
        self.bot.run(self.TOKEN)  # start the bot

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run a Discord bot.')
    parser.add_argument('--token-env-var', help='The name of the environment variable that stores the bot token.')
    parser.add_argument('--log', help='The file to log output to.')
    args = parser.parse_args()

    bot = Bot(token_env_var=args.token_env_var, log_file=args.log)
    bot.run()

