import os
import subprocess
import threading
import logging
import logging.config
import shutil
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import json
import dotenv
import multiprocessing
import socket
from botbase import BotBase
from testbot import TestBot
from gptbot import GPTBot


class Manager:
    def __init__(self):
        self.bot_processes = {}
        self.client_threads = []
        self.shutdown = False
        # Configure server socket for communication with bots
        self.client_sockets = {} # Store client sockets for each bot
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('localhost', 5000))  # Bind to localhost on port 5000
        self.server_thread = threading.Thread(target=self.start_server)
        self.server_thread.start()

        self.initialize_manager()
        self.root.mainloop()  # Start the GUI
        
        # Wait for any spawned threads to finish
        self.server_thread.join()
        for thread in self.client_threads:
            thread.join()

    def start_server(self):
        self.server_socket.listen()
        self.server_socket.settimeout(1)
        while not self.shutdown:
            try:
                client_socket, address = self.server_socket.accept() # Accept incoming connections (blocking call)
                client_thread = threading.Thread(target=self.handle_connection, args=(client_socket,))
                client_thread.start()
            except socket.timeout:
                continue

    def handle_connection(self, client_socket):
        client_socket.settimeout(1)  # Set a timeout of 1 second
        bot_name = None
        while not self.shutdown:
            try:
                message = client_socket.recv(1024)
                if not message:
                    break
                
                if not bot_name: # If we don't have a bot name yet, get it from the first message
                    bot_name = json.loads(message.decode("utf-8")).get("bot_name")
                    self.client_sockets[bot_name] = client_socket
                    logging.info(f"Connected to bot {bot_name}")

                # TODO: Process messages from the client bots here
            except socket.timeout:
                continue

    def initialize_manager(self):
        """Load environment variables, configure logging, load bots, and initialize GUI."""
        dotenv.load_dotenv()  # Load environment variables from .env file
        self.configure_logging()
        self.bot_config = self.get_bot_configuration()
        self.initialize_gui()

    def configure_logging(self):
        """Configure the logging system by reading the logging configuration from the logging.json file."""
        if not os.path.exists("logging"):
            os.makedirs("logging", exist_ok=True)
        try:
            with open("logging.json", "r") as f:
                log_config = json.load(f)
            date_prefix = datetime.now().strftime("%Y-%m-%d")
            class_name = self.__class__.__name__
            filename = (
                log_config["handlers"]["default"]["filename"]
                .replace("{date}", date_prefix)
                .replace("{name}", class_name)
            )
            log_config["handlers"]["default"]["filename"] = os.path.join(
                "logging", filename
            )
            logging.config.dictConfig(log_config)
        except Exception as e:
            logging.error(f"Failed to configure logging: {e}")

    def get_bot_configuration(self):
        """Load bot names and environment variable names from a JSON file."""
        if not os.path.exists("bots.json"):
            logging.error(
                "Failed to load bot configuration: bots.json file does not exist."
            )
            return None
        try:
            with open("bots.json", "r") as f:
                bots_config = json.load(f)
            return bots_config
        except Exception as e:
            logging.error(f"Failed to load bot configuration: {e}")
            return None

    def get_bot_log_file(self, bot_name):
        """Get the most recent log file for a bot."""
        log_dir = "logging"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        log_files = [f for f in os.listdir(log_dir) if bot_name in f]
        if not log_files:
            return None
        latest_log_file = max(log_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
        return os.path.join(log_dir, latest_log_file)

    def initialize_gui(self):
        """Initialize the GUI. Create a new Tk root window and add a Start Bot, Stop Bot, Open Bot Log, and Open Manager Log button for each bot."""
        self.root = tk.Tk()  # Initialize the root window here
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup)
        self.root.title("Bot Manager")  # Set the window title
        self.root.geometry("400x400")  # Set initial window size

        # Add a button to open the manager log
        open_manager_log_button = tk.Button(
            self.root, text="Open Manager Log", command=self.open_manager_log
        )
        open_manager_log_button.pack(side="top")

        # Add a button to clear all logs
        clear_logs_button = tk.Button(
            self.root, text="Clear Logs", command=self.clear_logs
        )
        clear_logs_button.pack(side="top")

        # Create a canvas and a vertical scrollbar for scrolling
        canvas = tk.Canvas(self.root)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        # Configure the canvas to be scrollable
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Pack the scrollbar and the canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # Define the button actions and their corresponding methods
        self.actions = [
            {"name": "Start", "method": self.start_bot},
            {"name": "Stop", "method": self.stop_bot},
            {"name": "Open Log", "method": self.open_log},
        ]

        # Create a frame for each bot
        for i, bot in enumerate(self.bot_config):
            frame = tk.Frame(scrollable_frame)
            frame.grid(
                row=i, column=0, padx=10, pady=10
            )  # Add padding and place the frame in the grid

            # Create a label for the bot name
            label = tk.Label(frame, text=bot['name'], anchor="e", width=20)
            label.grid(row=0, column=0)
            # Create buttons for each action and map the event to the corresponding action method
            for j, action in enumerate(self.actions):
                button = tk.Button(
                    frame,
                    text=action["name"],
                    command=lambda bot=bot, action=action: action["method"](
                        bot['name']
                    ),
                )
                button.grid(row=0, column=j + 1)

    def open_manager_log(self):
        """Open the manager log file in Notepad++ or Notepad."""
        today = datetime.now().strftime("%Y-%m-%d")  # Get today's date
        manager_log_file = os.path.join(
            "logging", f"{today}_manager.log"
        )  # Use today's date to create the filename
        if not os.path.exists(manager_log_file):
            logging.error(f"Manager log file does not exist.")
            return
        try:
            subprocess.Popen(["notepad++.exe", manager_log_file])
            logging.info(f"Opened manager log in Notepad++")
        except FileNotFoundError:
            try:
                subprocess.Popen(["notepad.exe", manager_log_file])
                logging.info(f"Opened manager log in Notepad")
            except FileNotFoundError:
                logging.error(
                    f"Failed to open manager log file. Please ensure that Notepad or Notepad++ is installed."
                )

    def clear_logs(self):
        """Delete all log files."""
        log_dir = "logging"
        if not os.path.exists(log_dir):
            return

        # Get the root logger
        logger = logging.getLogger()

        # Load the logging configuration
        with open("logging.json", "r") as f:
            log_config = json.load(f)

        for filename in os.listdir(log_dir):
            try:
                # Stop the logger
                log_file_path = os.path.abspath(os.path.join(log_dir, filename))
                for handler in logger.handlers[:]:  # Make a copy of the list because we're modifying it while iterating
                    if isinstance(handler, logging.handlers.TimedRotatingFileHandler) and handler.baseFilename == log_file_path:
                        handler.close()
                        logger.removeHandler(handler)

                # Delete the file
                os.remove(log_file_path)

                if os.path.exists(log_file_path):
                    logging.error(f"Failed to delete {filename}. Validate the file is closed in notepad.")

                # Create a new formatter with the loaded configuration
                new_handler = logging.handlers.TimedRotatingFileHandler(log_file_path, when="midnight")
                formatter_config = log_config["formatters"]["standard"]
                new_handler.setFormatter(logging.Formatter(formatter_config["format"], datefmt=formatter_config["datefmt"]))

                logger.addHandler(new_handler)

            except Exception as e:
                logging.error(f"Failed to delete {filename}. Reason: {e}")
        
        logging.info("All log files have been deleted.")

    def start_bot(self, bot_name):
        # Check if the bot is already running
        if bot_name in self.bot_processes:
            logging.warning(f"Bot {bot_name} is already running.")
            return
        
        bot_config = next((bot for bot in self.bot_config if bot['name'] == bot_name), None)
        if bot_config is None:
            logging.error(f"No configuration found for bot {bot_name}")
            return

        # Start the bot in a new process
        process = multiprocessing.Process(
            target=self.run_bot_process,
            args=(bot_config, self.server_socket.getsockname()),
        )
        process.start()
        self.bot_processes[bot_name] = process

    def run_bot_process(self, config, server_address):
        # Create the bot (this method is called in another thread so the bot can run without blocking)
        bot_type = config.get("type")

        if bot_type == "TestBot":
            bot = TestBot(config, server_address)
        elif bot_type == "GPTBot":
            bot = GPTBot(config, server_address)
        else:
            raise ValueError(f"Unknown bot type: {bot_type}")
        bot.run()

    def stop_bot(self, bot_name):
        """Stop a bot by sending a stop message over the socket."""
        if bot_name in self.client_sockets:
            message = {"command": "stop"}
            message_bytes = json.dumps(message).encode("utf-8")
            self.client_sockets[bot_name].sendall(message_bytes)

    def cleanup(self):
        """Cleanup function to stop all bots and close the GUI."""
        for bot_type in self.bot_processes:
            self.stop_bot(bot_type)
            self.bot_processes[bot_type].join(timeout=5)
            if self.bot_processes[bot_type].is_alive():
                logging.warning(
                    f"Bot {bot_type} did not stop within the timeout period."
                )
        self.root.destroy()
        self.shutdown = True

    def open_log(self, bot_name):
        """Open the log file for a bot in Notepad++ or Notepad."""
        bot_log_file = self.get_bot_log_file(bot_name)
        if not os.path.exists(bot_log_file):
            logging.error(f"Log file for bot {bot_name} does not exist.")
            return
        try:
            subprocess.Popen(["notepad++.exe", bot_log_file])
            logging.info(f"Opened log for bot {bot_name} in Notepad++")
        except FileNotFoundError:
            try:
                subprocess.Popen(["notepad.exe", bot_log_file])
                logging.info(f"Opened log for bot {bot_name} in Notepad")
            except FileNotFoundError:
                logging.error(
                    f"Failed to open log file for bot {bot_name}. Please ensure that Notepad or Notepad++ is installed."
                )


# This block of code will only run if this script is executed directly from the command line.
# It creates an instance of the Manager class, which will call the constructor function above and start the GUI.
if __name__ == "__main__":
    manager = Manager()
