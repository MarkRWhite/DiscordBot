import os
import subprocess
import platform
import threading
import logging
import logging.config
import time
import psutil
import select
import sys
from datetime import datetime
import tkinter as tk
import json
import socket

class Manager:
    def __init__(self):
        self.bot_processes = {}
        self.client_threads = []
        self.shuttingdown = False
        self.configure_logging()
        self.load_configuration()
        self.initialize_gui()

        # Configure server socket for communication with bots
        self.client_sockets = {} # Store client sockets for each bot
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(self.server_address)  # Bind to localhost on port 5000
        self.server_thread = threading.Thread(target=self.start_server)
        self.server_thread.start()

        self.root.mainloop()  # Start the GUI (BLOCKING)
        
        # Wait for any spawned threads to finish
        self.server_thread.join()
        for thread in self.client_threads:
            thread.join()

    def start_server(self):
        self.server_socket.listen()
        while not self.shuttingdown:
            try:
                readable, _, _ = select.select([self.server_socket], [], [], 1)
                if readable:
                    client_socket, address = self.server_socket.accept()
                    client_thread = threading.Thread(target=self.handle_connection, args=(client_socket,))
                    client_thread.start()
            except Exception as e:
                logging.error(f"Failed to accept client connection: {e}")

    def handle_connection(self, client_socket):
        client_socket.setblocking(False)  # Set to non-blocking
        buffer = b""
        while not self.shuttingdown:
            readable, _, _ = select.select([client_socket], [], [], 1)
            if readable:
                data = client_socket.recv(1024)
                if not data:
                    # Client disconnected
                    for bot_id, socket in list(self.client_sockets.items()):
                        if socket == client_socket:
                            del self.client_sockets[bot_id]
                    break
                buffer += data
                while b'\n' in buffer:
                    message, buffer = buffer.split(b'\n', 1)
                    self.process_message(message, client_socket)

    def process_message(self, message, client_socket):
        try:
            message = json.loads(message)
            if 'bot_id' in message:
                bot_id = message['bot_id']
                if bot_id in self.client_sockets:
                    # If bot_id is already in client_sockets, validate that it matches the bot_id associated with the client_socket
                    if self.client_sockets[bot_id] != client_socket:
                        logging.error(f"Received message with bot_id {bot_id} from unexpected client_socket")
                else:
                    # If bot_id is not in client_sockets, add it
                    self.client_sockets[bot_id] = client_socket
            else:
                logging.error(f"Received message without bot_id: {message}")
        except json.JSONDecodeError:
            logging.error(f"Failed to decode message: {message}")

    def load_configuration(self):
        """Load configurations from config.json."""
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
            host = self.config.get("Manager", {}).get("host")
            port = self.config.get("Manager", {}).get("port")
            self.server_address = (host, port)  # Use the host and port from the config file
            self.bot_config = self.config.get("Bots", {})
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}")

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

    def get_bot_log_file(self, bot_id):
        """Get the most recent log file for a bot."""
        log_dir = "logging"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        log_files = [f for f in os.listdir(log_dir) if bot_id in f]
        if not log_files:
            return None
        latest_log_file = max(log_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
        return os.path.join(log_dir, latest_log_file)

    def initialize_gui(self):
        """Initialize the GUI. Create a new Tk root window and add a Start Bot, Stop Bot, Open Bot Log, and Open Manager Log button for each bot."""
        self.root = tk.Tk()  # Initialize the root window here
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
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
        for i, (bot_id, bot) in enumerate(self.config.get("Bots", {}).items()):
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
                    command=lambda bot_id=bot_id, action=action: action["method"](bot_id)
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
                log_file_path = os.path.abspath(os.path.join(log_dir, filename))

                # Get handlers which have a baseFilename set to log_file_path
                handlers = [handler for handler in logger.handlers if isinstance(handler, logging.handlers.TimedRotatingFileHandler) and handler.baseFilename == log_file_path]

                if not handlers:
                    # No handler is associated with the file, delete it immediately
                    os.remove(log_file_path)
                    if os.path.exists(log_file_path):
                        logging.error(f"Failed to delete {filename}. Validate the file is closed in notepad.")
                    continue

                for handler in handlers:
                    # Remove the handler from the logger
                    logger.removeHandler(handler)
                    handler.close()

                    # Check if the handler is properly closed
                    if handler.stream is not None and not handler.stream.closed:
                        logging.error(f"Failed to close the handler for {filename}.")
                        continue

                    # Delete the file
                    os.remove(log_file_path)
                    if os.path.exists(log_file_path):
                        logging.error(f"Failed to delete {filename}. Validate the file is closed in notepad.")

                    # Recreate a new handler with the loaded configuration
                    new_handler = logging.handlers.TimedRotatingFileHandler(log_file_path, when="midnight")
                    formatter_config = log_config["formatters"]["standard"]
                    new_handler.setFormatter(logging.Formatter(formatter_config["format"], datefmt=formatter_config["datefmt"]))

                    logger.addHandler(new_handler)
            except Exception as e:
                logging.error(f"Failed to delete {filename}. Reason: {e}")

    def start_bot(self, bot_id):
        """Start a bot process."""
        bot_config = self.bot_config.get(bot_id)
        if not bot_config:
            logging.error(f"No configuration found for bot {bot_id}")
            return

        if bot_id in self.bot_processes and self.bot_processes[bot_id].poll() is None:
            logging.error(f"Bot {bot_id} is already running.")
            return

        try:
            # Construct the launch command to start the bot
            python_path = self.config['Manager']['pythonpath']
            command = [python_path] + [f"{bot_config['type']}.py", "--bot_id", bot_id]

            # Load the existing bot process information
            os.makedirs('temp', exist_ok=True)
            if os.path.exists('temp/bot_process_info.json'):
                with open('temp/bot_process_info.json', 'r') as f:
                    data = json.load(f)
            else:
                data = {}

            # Check if the last stored process information associated with this bot_id is still running
            bot_info = data.get(bot_id, {})
            pid = bot_info.get('pid')
            command_str = ' '.join(command)
            if pid and psutil.pid_exists(pid):
                p = psutil.Process(pid)
                if p.status() != psutil.STATUS_ZOMBIE:
                    logging.error(f"Bot {bot_id} is already running with PID {pid}.")
                    return
                else:
                    p.terminate()
                    p.wait(timeout=5)

            # Start the bot process
            print("DEBUG PATH: " + ' '.join(command))
            bot_process = subprocess.Popen(command)
            self.bot_processes[bot_id] = bot_process
            logging.info(f"Started bot {bot_id}")

            # Update the bot process information temp file with the new process information
            data[bot_id] = {'pid': bot_process.pid, 'command': command_str, 'timestamp': time.time()}
            with open('temp/bot_process_info.json', 'w') as f:
                json.dump(data, f)

        except Exception as e:
            logging.error(f"Failed to start bot {bot_id}: {e}")

    def stop_bot(self, bot_id):
        """Stop a bot by sending a stop message over the socket."""
        try:
            if bot_id in self.client_sockets:
                message = {"command": "stop"}
                message_bytes = json.dumps(message).encode("utf-8")
                self.client_sockets[bot_id].sendall(message_bytes)
        except Exception as e:
            logging.error(f"Failed to stop bot {bot_id}. Reason: {e}")

    def kill_bot(self, bot_id):
        # Load the data from the file
        with open('temp/bot_process_info.json', 'r') as f:
            data = json.load(f)

        # Get the bot's information using the bot_id key
        bot_info = data.get(bot_id, {})

        pid = bot_info.get('pid')
        command = bot_info.get('command')

        if pid and command:
            if psutil.pid_exists(pid):
                p = psutil.Process(pid)
                if ' '.join(p.cmdline()) == command:
                    p.terminate()
                    logging.info(f"Killed bot {bot_id}")
                else:
                    logging.error(f"PID {pid} is not associated with bot {bot_id}")
            else:
                logging.error(f"Bot {bot_id} is not running")
        else:
            logging.error(f"No information found for bot {bot_id}")

    def shutdown(self):
        """Shutdown the manager and stop all bots if stopBotsOnShutdown is True."""
        self.shuttingdown = True
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}")
            return
        stop_bots_on_shutdown = config.get("Manager", {}).get("stopBotsOnShutdown", False)
        if stop_bots_on_shutdown:
            for bot_id, bot_process in self.bot_processes.items():
                if bot_process.poll() is None:
                    bot_process.terminate()
                    logging.info(f"Stopped bot {bot_id}")
        self.root.quit() # Escape the GUI mainloop

    def open_log(self, bot_id):
        """Open the log file for a bot in Notepad++ or Notepad."""
        log_file = self.get_bot_log_file(bot_id)
        if not log_file:
            logging.error(f"No log file found for bot {bot_id}.")
            return
        try:
            subprocess.Popen(["notepad++.exe", log_file])
            logging.info(f"Opened {bot_id} log in Notepad++")
        except FileNotFoundError:
            try:
                subprocess.Popen(["notepad.exe", log_file])
                logging.info(f"Opened {bot_id} log in Notepad")
            except FileNotFoundError:
                logging.error(
                    f"Failed to open {bot_id} log file. Please ensure that Notepad or Notepad++ is installed."
                )


# This block of code will only run if this script is executed directly from the command line.
# It creates an instance of the Manager class, which will call the constructor function above and start the GUI.
if __name__ == "__main__":
    manager = Manager()
