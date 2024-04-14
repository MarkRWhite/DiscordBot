import os
import subprocess
import logging
import logging.config
from datetime import datetime
import tkinter as tk
import json
import dotenv

class Manager:
    def __init__(self):
        self.bot_processes = {}
        self.log_file = None
        self.initialize_manager()
        self.root.mainloop() #Start the GUI

    def initialize_manager(self):
        """Load environment variables, configure logging, load bots, and initialize GUI."""
        dotenv.load_dotenv()
        self.configure_logging()
        self.bots = self.get_bot_configuration()
        self.initialize_gui()

    def configure_logging(self):
        """Configure the logging system by reading the logging configuration from the logging.json file."""
        try:
            with open('logging.json', 'r') as f:
                log_config = json.load(f)
            date_prefix = datetime.now().strftime('%Y-%m-%d')
            log_config['handlers']['default']['filename'] = log_config['handlers']['default']['filename'].replace('{date}', date_prefix)
            self.log_file = log_config['handlers']['default']['filename']
            logging.config.dictConfig(log_config)
        except Exception as e:
            logging.error(f"Failed to configure logging: {e}")

    def get_bot_configuration(self):
        """Load bot names and environment variable names from a JSON file."""
        try:
            with open('bots.json', 'r') as f:
                bots = json.load(f)
            for bot_name, bot_config in bots.items():
                env_token_key = bot_config.get('envtoken')
                if env_token_key:
                    logging.info(f"Bot name: {bot_name}, Token env var: {env_token_key}")
            return bots
        except FileNotFoundError:
            logging.error("Failed to load bot configuration. Please ensure that bots.json is present.")
            return None

    def get_bot_log_file(self, bot_name):
        """Generate the log file path for a bot."""
        date_prefix = datetime.now().strftime('%Y-%m-%d')
        bot_log_file = os.path.join('logging', f'{date_prefix}_bot_{bot_name}.log')
        if not os.path.exists(bot_log_file):
            os.makedirs(os.path.dirname(bot_log_file), exist_ok=True)
            with open(bot_log_file, 'w') as f:
                pass
        return bot_log_file

    def initialize_gui(self):
        """Initialize the GUI. Create a new Tk root window and add Start Bot, Stop Bot, and Open Log buttons to it for each bot."""
        self.root = tk.Tk()
        self.root.title("Bot Manager")
        for bot_name in self.bots:
            frame = tk.Frame(self.root)
            frame.pack()
            start_button = tk.Button(frame, text=f"Start {bot_name}", command=lambda bot_name=bot_name: self.start_bot(bot_name))
            start_button.pack(side=tk.LEFT)
            stop_button = tk.Button(frame, text=f"Stop {bot_name}", command=lambda bot_name=bot_name: self.stop_bot(bot_name))
            stop_button.pack(side=tk.LEFT)
            open_log_button = tk.Button(frame, text=f"Open {bot_name} Log", command=lambda bot_name=bot_name: self.open_log(bot_name))
            open_log_button.pack(side=tk.LEFT)

    def start_bot(self, bot_name):
        """Start a bot by executing the bot.py script in a separate process."""
        try:
            bot_log_file = self.get_bot_log_file(bot_name)
            env_token_key = self.bots[bot_name].get('envtoken')
            self.bot_processes[bot_name] = subprocess.Popen(['python', 'bot.py', '--log', bot_log_file, '--token-env-var', env_token_key])
            logging.info(f"Started bot {bot_name}")
        except (FileNotFoundError, subprocess.CalledProcessError):
            logging.error(f"Failed to start bot {bot_name}. Please ensure that bot.py is present and can be executed.")

    def stop_bot(self, bot_name):
        """Stop a bot by terminating its process."""
        if bot_name in self.bot_processes:
            self.bot_processes[bot_name].terminate()
            del self.bot_processes[bot_name]
            logging.info(f"Stopped bot {bot_name}")

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