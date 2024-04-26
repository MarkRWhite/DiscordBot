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
from queue import Queue
from abc import ABC, abstractmethod

import asyncio
import discord
from discord.ext import commands
import dotenv


class BotBase(ABC):

    def __init__(self, bot_id=None):
        self.bot_id = bot_id or self.__class__.__name__
        self.bot_thread = None
        self._running = False
        self.manager_socket = None # Socket to communicate with Manager
        self.ack_condition = threading.Condition() # Condition to wait for message ACK from Manager
        self.message_queue = Queue() # Queue for incoming messages
        self.queue_lock = threading.Lock() # Lock for the message queue
        self.waiting_for_ack = False # Flag to indicate if we are waiting for an ACK
        self.setup_logging() # Run this before anything that might log
        self.config = self.load_config()
        
        address = self.config.get("Manager", {}).get("host"), self.config.get("Manager", {}).get("port")
        self.server_address = (address) if self.config.get("Manager") else None

        envtoken = self.config.get("Bots", {}).get(self.bot_id, {}).get("envtoken")
        if not envtoken:
            raise ValueError("envtoken argument is required.")

        dotenv.load_dotenv()  # Load environment variables from .env file
        self.TOKEN = os.getenv(envtoken)
        if not self.TOKEN:
            raise ValueError(f"Environment variable {self.config.get("envtoken")} is not set.")

        self.discord_setup()

    def start_communication_thread(self):
        self.communication_thread = threading.Thread(target=self.communication_loop)
        self.communication_thread.start()

    def communication_loop(self):
        while self._running:
            ready_to_read, _, _ = select.select([self.manager_socket], [], [], 1)
            if ready_to_read:
                try:
                    message = self.manager_socket.recv(1024).decode('utf-8')
                    if message and message != 'OK':
                        ack_message = json.dumps({"status": "OK", "bot_id": self.bot_id})
                        self.manager_socket.sendall(ack_message.encode('utf-8')) # ACK
                        with self.queue_lock: # Acquire the lock before adding to the queue
                            self.message_queue.put(json.loads(message)) # Add message to the queue
                    elif message == 'OK':
                        if self.waiting_for_ack:
                            logging.info("Received ACK from Manager.")
                        else:
                            logging.warning("Received unexpected ACK from Manager.")
                        with self.ack_condition:
                            self.waiting_for_ack = False # Release the ACK condition
                            self.ack_condition.notify_all()
                except Exception as e:
                    logging.error(f"Error receiving message: {e}")
                    break

        logging.info("Communication thread is stopping.")

    def send_message(self, json):
        if self.manager_socket:
            logging.info(f"Sending message: {json}")
            try:
                self.manager_socket.sendall(json.encode('utf-8'))
                self.wait_for_ack()
            except Exception as e:
                logging.error(f"Error sending message: {e}")

    def create_socket(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.server_address)
            return s
        except Exception as e:
            logging.error(f"Error creating socket: {e}")
            return None
        
    def wait_for_ack(self, timeout=None):
        """Wait for an ACK from the Manager."""
        with self.ack_condition:
            self.waiting_for_ack = True
            while self.waiting_for_ack:
                self.ack_condition.wait(timeout)

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
        self._running = True

        # Setup communication with the manager
        self.manager_socket = self.create_socket() if self.server_address else None
        if self.manager_socket:
            self.start_communication_thread()
            connected_message = json.dumps({"status": "connected", "bot_id": self.bot_id})
            self.send_message(connected_message)
        else:
            logging.info("No server address provided. Running without a Manager.")

        self.discord_run()

        logging.info(f"Bot is running.")
        while self._running:
            with self.queue_lock: # Acquire the lock before accessing the queue
                if not self.message_queue.empty():
                    message = self.message_queue.get()
                    self.process_message(message) # Process incoming messages
            self.main_loop()
            time.sleep(0.1)

        logging.info(f"Bot is stopping.")

    @abstractmethod
    def main_loop(self):
        pass # TODO: # Override in base class to implement custom behavior

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
        # Called by discord when the bot is ready
        logging.info(f"We have logged in as {self.bot.user}")

    @commands.command()
    async def hello(self, ctx):
        await ctx.send("Hello!")

    @abstractmethod
    def shutdown(self):
        '''Shutdown the bot.'''
        logging.info("Shutting down the bot.")
        self._running = False
        self.discord_stop()

        if self.communication_thread.is_alive():
            self.communication_thread.join(timeout=5)  # wait for the communication thread to finish

        if self.communication_thread.is_alive():
            logging.error("Failed to stop the communication thread within the timeout period.")

    def discord_setup(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.initialize_bot_commands()

    def discord_run(self):
        logging.info("Starting the bot.")
        if self.bot_thread is None or not self.bot_thread.is_alive():
            self.bot_thread = threading.Thread(
                target=self.bot.run, args=(self.TOKEN,)
            )  # create a new thread to run the bot
            self.bot_thread.start()  # start the thread
        else:
            logging.error("The bot thread is already running.")

    def discord_stop(self):
        if self.bot.is_closed():
            logging.info("Bot is already stopped.")
            return

        logging.info("Stopping the bot.")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.bot.close())

        if self.bot_thread.is_alive():
            self.bot_thread.join(timeout=5)  # wait for the bot thread to finish

        if self.bot_thread.is_alive():
            logging.error("Failed to stop the bot thread within the timeout period.")
