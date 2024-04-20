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
        self.bot_sockets = {}
        self.shutdown = False
        self.initialize_manager()
        self.root.mainloop()  # Start the GUI

    def initialize_manager(self):
        """Load environment variables, configure logging, load bots, and initialize GUI."""
        dotenv.load_dotenv()  # Load environment variables from .env file
        self.configure_logging()
        self.bots = self.get_bot_configuration()
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
                bots = json.load(f)
            for bot_name, bot_config in bots.items():
                env_token_key = bot_config.get("envtoken")
                if env_token_key:
                    logging.info(
                        f"Bot name: {bot_name}, Token env var: {env_token_key}"
                    )
            return bots
        except Exception as e:
            logging.error(f"Failed to load bot configuration: {e}")
            return None

    def get_bot_log_file(self, bot_name):
        """Generate the log file path for a bot."""
        with open("logging.json", "r") as f:
            log_config = json.load(f)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        log_file = (
            log_config["handlers"]["default"]["filename"]
            .replace("{date}", date_prefix)
            .replace("{name}", bot_name)
        )
        log_file_path = os.path.join("logging", log_file)
        if not os.path.exists(log_file_path):
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            with open(log_file_path, "w") as f:
                pass
        return log_file_path

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

        # Define the actions and their corresponding methods
        self.actions = [
            {"name": "Start", "method": self.start_bot},
            {"name": "Stop", "method": self.stop_bot},
            {"name": "Open Log", "method": self.open_log},
        ]

        # Create a frame for each bot
        for i, bot_name in enumerate(self.bots):
            frame = tk.Frame(scrollable_frame)
            frame.grid(
                row=i, column=0, padx=10, pady=10
            )  # Add padding and place the frame in the grid

            # Create a label for the bot name
            label = tk.Label(frame, text=bot_name, anchor="e", width=20)
            label.grid(row=0, column=0)

            for j, action in enumerate(self.actions):
                button = tk.Button(
                    frame,
                    text=action["name"],
                    command=lambda bot_name=bot_name, action=action: action["method"](
                        bot_name
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
        """Clear all log files in the logging directory."""
        log_dir = "logging"
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logging.error(f"Failed to delete {file_path}. Reason: {e}")
        logging.info("Logs cleared.")

    def start_bot(self, bot_name):
        bot_type = self.bots[bot_name].get("type")
        bot_log_file = self.get_bot_log_file(bot_name)
        env_token_key = self.bots[bot_name].get("envtoken")

        # Create a new socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("localhost", 0))  # Bind to a random free port
        server_socket.listen(1)

        # Start the bot in a new process
        process = multiprocessing.Process(
            target=self.run_bot_process,
            args=(bot_type, env_token_key, bot_log_file, server_socket.getsockname()),
        )
        process.start()

        client_socket, _ = server_socket.accept()

        self.bot_processes[bot_type] = process
        self.bot_sockets[bot_type] = client_socket

    def send_message(self, bot_type, message):
        message_bytes = json.dumps(message).encode("utf-8")
        self.bot_sockets[bot_type].sendall(message_bytes)

    def receive_messages(self, bot_type):
        while not self.shutdown:
            message_bytes = self.bot_sockets[bot_type].recv(1024)

            # If no data is received, the client has closed the connection
            if not message_bytes:
                break

            # Convert the message from bytes to JSON
            message = json.loads(message_bytes.decode("utf-8"))

            # Process the message
            print(f"Received message: {message}")

    def run_bot_process(self, bot_type, env_token_key, bot_log_file, server_address):
        # Create the bot (this method is called in another thread so the bot can run without blocking)
        if bot_type == "TestBot":
            bot = TestBot(env_token_key, bot_log_file)
        elif bot_type == "GPTBot":
            bot = GPTBot(env_token_key, bot_log_file)
        else:
            raise ValueError(f"Unknown bot type: {bot_type}")
        bot.run()

    def stop_bot(self, bot_name):
        """Stop a bot by sending a stop message over the socket."""
        if bot_name in self.bot_sockets:
            message = {"command": "stop"}
            message_bytes = json.dumps(message).encode("utf-8")
            self.bot_sockets[bot_name].sendall(message_bytes)

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
