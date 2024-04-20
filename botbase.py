import argparse
import json
import logging
import os
import signal
import socket
import sys
import time
import datetime
import threading
from abc import ABC, abstractmethod

import asyncio
import discord
from discord.ext import commands
import dotenv


class BotBase(ABC):

    def __init__(self, config, server_address):
        self.config = config
        self.server_address = server_address
        self.setup_logging() # Run this before anything that might log

        if not self.config.get("token_env_var"):
            raise ValueError("token_env_var argument is required.")
        if not server_address:
            raise ValueError("server_address argument is required.")

        # Setup communication with the manager
        self.manager_socket = self.create_socket()
        self.send_connected_message() # TODO: Make a generic send_message method that can be used for all messages
        self.manager_listening = False
        self.retry_interval = 5  # Seconds - How often we try to reconnect to the manager
        self.lock = threading.Lock() # TODO: Implement thread locking for events on other threads that touch the bot object properties

        dotenv.load_dotenv()  # Load environment variables from .env file
        self.TOKEN = os.getenv(self.config.get("token_env_var"))
        if not self.TOKEN:
            raise ValueError(f"Environment variable {self.config.get("token_env_var")} is not set.")

        self.setup_discord()

    def create_socket(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(self.server_address)
            return s
        except Exception as e:
            logging.error(f"Error creating socket: {e}")
            return None

    def run(self):
        self.running = True
        self.start_manager_listener() # Start the listening thread for communication with the manager
        self.discord_run()

        # Main Run Loop
        while self.running:
            self.main_loop()

            # Restart communication with the manager
            current_time = time.time()
            if not self.manager_listening_thread.is_alive() and self.manager_listening:
                self.start_manager_listener()
                self.last_retry_time = current_time

            time.sleep(0.5)

        # Wait for any process threads to exit here before exiting the process
        if self.manager_listening_thread.is_alive():
            self.manager_listening = False
        self.manager_listening_thread.join()  # wait for the listening thread to exit

        logging.info(f"Bot is stopping.")

    def main_loop(self):
        pass # TODO: Main loop code actions go here

    def start_manager_listener(self):
        self.manager_listening = True
        self.manager_listening_thread = threading.Thread(target=self.manager_listen)  # Create a new thread instance
        self.manager_listening_thread.start()

    def send_connected_message(self):
        status_message = {"status": "connected", "bot_name": self.config.get("bot_name")} 
        self.manager_socket.sendall(json.dumps(status_message).encode("utf-8")) # The manager uses this message to identify the connecting bot

    def manager_listen(self):
        while self.manager_listening:
            try:
                message_bytes = self.manager_socket.recv(1024) # Receive message from manager
            except socket.timeout:
                continue
            except socket.error as e:
                logging.error(f"Socket error: {e}")
                break

            if not message_bytes:
                break; # Connection was closed from server

            message = json.loads(message_bytes.decode("utf-8"))
            self.process_message(message)

        logging.info("Listening thread is stopping.")

    @abstractmethod
    def process_message(self, message):
        # If a stop command is received, stop the bot
        if message.get("command") == "stop":
            self.shutdown()

    def setup_logging(self):
        with open("logging.json", "r") as f:
            config = json.load(f)
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        config["handlers"]["default"]["filename"] = f"{date}_{self.__class__.__name__}.log"
        logging.config.dictConfig(config)

    def setup_discord(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.initialize_bot_commands()

    @abstractmethod
    def initialize_bot_commands(self):
        self.commands = []
        # Add defaults
        self.commands.append("hello")
        self.bot.add_listener(self.on_ready)
        
        # Add custom commands from config
        custom_commands = self.config.get('commands', [])
        for command in custom_commands:
            if hasattr(self, command):
                self.commands.append(command)
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
        self.manager_listening = False
        self.manager_socket.shutdown(socket.SHUT_RDWR)  # shutdown the socket
        self.manager_socket.close()  # close the socket
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
