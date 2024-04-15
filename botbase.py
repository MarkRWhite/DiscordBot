import argparse
import json
import logging
import os
import signal
import sys
import threading
from abc import ABC, abstractmethod

import discord
from discord.ext import commands
import dotenv

class BotBase(ABC):
    def cleanup(self, signum, frame):
        # Perform cleanup operations here
        print("Bot is cleaning up...")
        # Create a task to close the bot
        self.bot.loop.create_task(self.bot.close())
        sys.exit(0)

    def __init__(self, token_env_var, log_file):
        signal.signal(signal.SIGINT, self.cleanup) # Set up cleanup signal handler so we can close the process gracefully
        dotenv.load_dotenv()  # Load environment variables from .env file

        self.log_file = log_file
        if not self.log_file:
            raise ValueError("log_file argument is required.")

        # Set up logging
        self.setup_logging()

        if not token_env_var:
            raise ValueError("token_env_var argument is required.")
        self.TOKEN = os.getenv(token_env_var)
        if not self.TOKEN:
            raise ValueError(f"Environment variable {token_env_var} is not set.")

        self.log_file = log_file
        if not self.log_file:
            raise ValueError("log_file argument is required.")

        # Setup bot
        self.initialize_bot_commands()

    def setup_logging(self):
        with open('logging.json', 'r') as f:
            config = json.load(f)
        config['handlers']['default']['filename'] = self.log_file
        logging.config.dictConfig(config)

    @abstractmethod
    def initialize_bot_commands(self):
        self.bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
        self.commands = []
        self.bot.add_listener(self.on_ready)
        for command in self.commands:
            self.bot.add_command(getattr(self, command))
    
    @abstractmethod
    async def on_ready(self):
        print(f'We have logged in as {self.bot.user}')

    @commands.command()
    async def hello(self, ctx):
        await ctx.send('Hello!')

    def run(self):
        logging.info("Starting the bot.")
        self.bot_thread = threading.Thread(target=self.bot.run, args=(self.TOKEN,))  # create a new thread to run the bot
        self.bot_thread.start()  # start the thread

    def stop(self):
        logging.info("Stopping the bot.")
        self.bot.loop.create_task(self.bot.close())
        self.bot_thread.join()  # wait for the bot thread to finish