import argparse
import json
import logging
import os
import signal
import socket
import sys
import time
import threading
from abc import ABC, abstractmethod

import asyncio
import discord
from discord.ext import commands
import dotenv


class BotBase(ABC):

    def __init__(self, token_env_var, log_file, server_address):
        self.token_env_var = token_env_var
        self.log_file = log_file
        self.server_address = server_address

        if not self.log_file:
            raise ValueError("log_file argument is required.")
        if not token_env_var:
            raise ValueError("token_env_var argument is required.")
        if not server_address:
            raise ValueError("server_address argument is required.")

        # Setup communication with the manager
        self.client_socket = self.create_socket()
        self.listening = False
        self.listening_thread = threading.Thread(target=self.listen_for_commands)
        self.lock = threading.Lock()

        dotenv.load_dotenv()  # Load environment variables from .env file
        self.TOKEN = os.getenv(token_env_var)
        if not self.TOKEN:
            raise ValueError(f"Environment variable {token_env_var} is not set.")

        self.setup_logging()
        self.setup_discord()

    def create_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(self.server_address)
        return client_socket

    def run(self):
        self.running = True
        self.start_listener()
        while self.running:
            # Run the bot
            pass

        logging.info(f"Bot is stopping.")

    def start_listener(self):
        self.listening = True
        self.listening_thread.start()

    def listen_for_commands(self):
        while self.listening:
            time.sleep(0.1)

            try:
                # Receive message from manager
                message_bytes = self.socket.recv(1024)
            except socket.error as e:
                logging.error(f"Socket error: {e}")
                break

            if not message_bytes:
                continue

            message = json.loads(message_bytes.decode("utf-8"))
            self.process_message(message)

        logging.info("Listening thread is stopping.")

    @abstractmethod
    def process_message(self, message):
        # If a stop command is received, stop the bot
        if message.get("command") == "stop":
            self.running = False
            self.listening = False

    def setup_logging(self):
        with open("logging.json", "r") as f:
            config = json.load(f)
        config["handlers"]["default"]["filename"] = self.log_file
        logging.config.dictConfig(config)

    def setup_discord(self, token):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.initialize_bot_commands()

    @abstractmethod
    def initialize_bot_commands(self):
        self.commands = []
        # Default commands
        self.commands.append("hello")

        self.bot.add_listener(self.on_ready)
        for command in self.commands:
            self.bot.add_command(getattr(self, command))

    @abstractmethod
    async def on_ready(self):
        print(f"We have logged in as {self.bot.user}")

    @commands.command()
    async def hello(self, ctx):
        await ctx.send("Hello!")

    def discord_run(self):
        logging.info("Starting the bot.")
        self.bot_thread = threading.Thread(
            target=self.bot.run, args=(self.TOKEN,)
        )  # create a new thread to run the bot
        self.bot_thread.start()  # start the thread

    def discord_stop(self, callback=None):
        if not self.bot.loop.is_closed():
            logging.info("Stopping the bot.")
            self.bot.loop.create_task(self.bot.close())

        if self.bot_thread.is_alive():
            self.bot_thread.join(timeout=5)  # wait for the bot thread to finish

        if self.bot_thread.is_alive():
            logging.error("Failed to stop the bot thread within the timeout period.")

        if callback is not None:
            callback()
