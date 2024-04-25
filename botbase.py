import argparse
import json
import logging
import logging.config
import os
import signal
import socket
import sys
import time
import datetime
import threading
import select
from abc import ABC, abstractmethod

import asyncio
import discord
from discord.ext import commands
import dotenv


class BotBase(ABC):

    def __init__(self, bot_id=None):
        self.bot_id = bot_id or self.__class__.__name__
        self.setup_logging() # Run this before anything that might log
        self.config = self.load_config()
        
        address = self.config.get("Manager", {}).get("host"), self.config.get("Manager", {}).get("port")
        self.server_address = (address) if self.config.get("Manager") else None

        envtoken = self.config.get("Bots", {}).get(self.bot_id, {}).get("envtoken")
        if not envtoken:
            raise ValueError("envtoken argument is required.")
        
        # Setup communication with the manager
        self.manager_socket = self.create_socket() if self.server_address else None
        if self.manager_socket:
            self.send_connected_message() 
        else:
            logging.info("No server address provided. Running without a Manager.")

        dotenv.load_dotenv()  # Load environment variables from .env file
        self.TOKEN = os.getenv(envtoken)
        if not self.TOKEN:
            raise ValueError(f"Environment variable {self.config.get("envtoken")} is not set.")

        self.setup_discord()

    def create_socket(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.server_address)
            return s
        except Exception as e:
            logging.error(f"Error creating socket: {e}")
            return None
        
    def load_config(self):
        """Load the full configuration from the config.json file."""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}")
            return {}

        return config

    def run(self):
        self.running = True
        self.discord_run()

        # Main Run Loop
        while self.running:
            self.main_loop()
            time.sleep(0.5)

        logging.info(f"Bot is stopping.")

    @abstractmethod
    def main_loop(self):
        pass # TODO: Main loop code actions go here

    def send_connected_message(self):
        if self.manager_socket:
            status_message = {"status": "connected", "bot_id": self.bot_id}
            try:
                self.manager_socket.sendall(json.dumps(status_message).encode("utf-8"))
                response = self.manager_socket.recv(1024).decode('utf-8')
                if response != 'OK':
                    logging.error(f"Failed to connect to manager: {response}")
            except Exception as e:
                logging.error(f"Error sending message: {e}")

    @abstractmethod
    def process_message(self, message):
        # If a stop command is received, stop the bot
        if message.get("command") == "stop":
            self.shutdown()

    def setup_logging(self):
        with open("logging.json", "r") as f:
            config = json.load(f)

        # Create logging directory if it doesn't exist
        logs_dir = "logging"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        date = datetime.datetime.now().strftime("%Y-%m-%d")
        config["handlers"]["default"]["filename"] = os.path.join(logs_dir, f"{date}_{self.bot_id}.log")
        logging.config.dictConfig(config)

    def setup_discord(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.initialize_bot_commands()

    @abstractmethod
    def initialize_bot_commands(self):
        # Add defaults
        self.bot.add_command(self.hello)
        self.bot.add_listener(self.on_ready)
        
        # Add custom commands from config
        custom_commands = self.config.get('commands', [])
        for command in custom_commands:
            if hasattr(self, command):
                self.bot.add_command(getattr(self, command))
            else:
                logging.warning(f"Command {command} not found in bot methods.")

    @abstractmethod
    async def on_ready(self):
        print(f"We have logged in as {self.bot.user}")

    @commands.command()
    async def hello(self, ctx):
        await ctx.send("Hello!")

    @abstractmethod
    def shutdown(self):
        # TODO: Add thread locking for the shutdown process
        self.running = False
        self.discord_stop()

    def discord_run(self):
        logging.info("Starting the bot.")
        self.bot_thread = threading.Thread(
            target=self.bot.run, args=(self.TOKEN,)
        )  # create a new thread to run the bot
        self.bot_thread.start()  # start the thread

    def discord_stop(self):
        if not self.bot.loop.is_closed():
            logging.info("Stopping the bot.")
            self.bot.loop.create_task(self.bot.close())

        if self.bot_thread.is_alive():
            self.bot_thread.join(timeout=5)  # wait for the bot thread to finish

        if self.bot_thread.is_alive():
            logging.error("Failed to stop the bot thread within the timeout period.")
