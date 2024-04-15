import os
import subprocess
import logging
import logging.config
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import json
import dotenv
from botbase import BotBase
from testbot import TestBot
from gptbot import GPTBot
class Manager:
    def __init__(self):
        self.bot_processes = {}
        self.initialize_manager()
        self.root.mainloop() #Start the GUI

    def initialize_manager(self):
        """Load environment variables, configure logging, load bots, and initialize GUI."""
        dotenv.load_dotenv() # Load environment variables from .env file
        self.configure_logging()
        self.bots = self.get_bot_configuration()
        self.initialize_gui()

    def configure_logging(self):
        """Configure the logging system by reading the logging configuration from the logging.json file."""
        if not os.path.exists("logging"):
            os.makedirs("logging", exist_ok=True)
        try:
            with open('logging.json', 'r') as f:
                log_config = json.load(f)
            date_prefix = datetime.now().strftime('%Y-%m-%d')
            class_name = self.__class__.__name__
            filename = log_config['handlers']['default']['filename'].replace('{date}', date_prefix).replace('{name}', class_name)
            log_config['handlers']['default']['filename'] = os.path.join('logging', filename)
            logging.config.dictConfig(log_config)
        except Exception as e:
            logging.error(f"Failed to configure logging: {e}")

    def get_bot_configuration(self):
        """Load bot names and environment variable names from a JSON file."""
        if not os.path.exists('bots.json'):
            logging.error("Failed to load bot configuration: bots.json file does not exist.")
            return None
        try:
            with open('bots.json', 'r') as f:
                bots = json.load(f)
            for bot_name, bot_config in bots.items():
                env_token_key = bot_config.get('envtoken')
                if env_token_key:
                    logging.info(f"Bot name: {bot_name}, Token env var: {env_token_key}")
            return bots
        except Exception as e:
            logging.error(f"Failed to load bot configuration: {e}")
            return None

    def get_bot_log_file(self, bot_name):
        """Generate the log file path for a bot."""
        with open('logging.json', 'r') as f:
            log_config = json.load(f)
        date_prefix = datetime.now().strftime('%Y-%m-%d')
        log_file = log_config['handlers']['default']['filename'].replace('{date}', date_prefix).replace('{name}', bot_name)
        log_file_path = os.path.join('logging', log_file)
        if not os.path.exists(log_file_path):
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            with open(log_file_path, 'w') as f:
                pass
        return log_file_path

    def initialize_gui(self):
        """Initialize the GUI. Create a new Tk root window and add a Start Bot, Stop Bot, and Open Log button for each bot."""
        self.root = tk.Tk()  # Initialize the root window here
        self.root.title("Bot Manager")  # Set the window title
        self.root.geometry('400x400')  # Set initial window size

        # Create a canvas and a vertical scrollbar for scrolling
        canvas = tk.Canvas(self.root)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        # Configure the canvas to be scrollable
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Pack the scrollbar and the canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # Define the actions and their corresponding methods
        self.actions = [
            {"name": "Start", "method": self.start_bot},
            {"name": "Stop", "method": self.stop_bot},
            {"name": "Open Log", "method": self.open_log},
        ]

        # Create a frame for each bot
        for i, bot_name in enumerate(self.bots):
            frame = tk.Frame(scrollable_frame)
            frame.grid(row=i, column=0, padx=10, pady=10)  # Add padding and place the frame in the grid

            # Create a label for the bot name
            label = tk.Label(frame, text=bot_name, anchor='e', width=20)
            label.grid(row=0, column=0)

            for j, action in enumerate(self.actions):
                button = tk.Button(frame, text=action["name"], command=lambda bot_name=bot_name, action=action: action["method"](bot_name))
                button.grid(row=0, column=j+1)

    def start_bot(self, bot_name):
        try:
            bot_type = self.bots[bot_name].get('type')
            bot_log_file = self.get_bot_log_file(bot_name)
            env_token_key = self.bots[bot_name].get('envtoken')

            if bot_type == 'TestBot':
                bot = TestBot(env_token_key, bot_log_file)
            elif bot_type == 'GPTBot':
                bot = GPTBot(env_token_key, bot_log_file)
            else:
                raise ValueError(f"Unknown bot type: {bot_type}")

            self.bot_processes[bot_name] = bot
            bot.run()
            logging.info(f"Started bot {bot_name}")
        except Exception as e:
            logging.error(f"Failed to start bot {bot_name}. Error: {e}")

    def stop_bot(self, bot_name):
        """Stop a bot by terminating its process."""
        if bot_name in self.bot_processes:
            bot = self.bot_processes[bot_name]
            bot.stop()
            del self.bot_processes[bot_name]

    def open_log(self, bot_name):
        """Open the log file for a bot in Notepad++ or Notepad."""
        bot_log_file = self.get_bot_log_file(bot_name)
        if not os.path.exists(bot_log_file):
            logging.error(f"Log file for bot {bot_name} does not exist.")
            return
        try:
            subprocess.Popen(['notepad++.exe', bot_log_file])
            logging.info(f"Opened log for bot {bot_name} in Notepad++")
        except FileNotFoundError:
            try:
                subprocess.Popen(['notepad.exe', bot_log_file])
                logging.info(f"Opened log for bot {bot_name} in Notepad")
            except FileNotFoundError:
                logging.error(f"Failed to open log file for bot {bot_name}. Please ensure that Notepad or Notepad++ is installed.")

# This block of code will only run if this script is executed directly from the command line.
# It creates an instance of the Manager class, which will call the constructor function above and start the GUI.
if __name__ == "__main__":
    manager = Manager()