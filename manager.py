import os
import subprocess
import threading
import logging
import logging.config
import time
import psutil
from datetime import datetime
import tkinter as tk
import json
import socket
import socketserver

class Manager:
    def __init__(self):
        self.bot_processes = {}
        self.client_sockets = {}
        self.client_sockets_lock = threading.RLock()  # Add a lock for client_sockets thread safety
        self.shuttingdown = False
        self.configure_logging()
        self.load_configuration()
        self.initialize_gui()
        
        try:
            # Configure server socket for communication with bots
            self.server = socketserver.ThreadingTCPServer(self.server_address, self.process_message)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.start()
        except socket.error as e:
            logging.error(f"Failed to start server: {e}")
            self.server = None

        self.root.mainloop()  # Start the GUI (BLOCKING)
        
        # Wait for server thread to finish
        #TODO: Stop bot processes
        self.server.shutdown()
        self.server_thread.join()

    def process_message(self, request, client_address, server):
        request.settimeout(5.0)
        try:
            data = request.recv(1024).strip()
            message = json.loads(data.decode('utf-8'))
            logging.info(f"Received message: {message}")
            bot_id = message.get('bot_id')
            if bot_id:
                with self.client_sockets_lock:  # Acquire the lock before accessing client_sockets
                    if bot_id in self.client_sockets and self.client_sockets[bot_id] != request:
                        logging.error(f"Received message with bot_id {bot_id} from unexpected client_socket")
                    else:
                        # If bot_id is not in client_sockets, add it
                        self.client_sockets[bot_id] = request
                        if message.get('status') == 'connected':
                            # Send an 'OK' message back to the bot
                            self.send_message(bot_id, 'OK')
            else:
                logging.error(f"Received message without bot_id: {message}")
        except json.JSONDecodeError:
            logging.error(f"Failed to decode message: {message}")
        except socket.timeout:
            logging.error("Client did not send data within the timeout period")

    def send_message(self, bot_id, message):
        logging.info(f"Sending message to bot {bot_id}: {message}")
        with self.client_sockets_lock:  # Acquire the lock before accessing client_sockets
            if bot_id in self.client_sockets:
                try:
                    # Try to send the message
                    self.client_sockets[bot_id].sendall(message.encode('utf-8'))
                except OSError as e:
                    if e.winerror == 10038:
                        # The socket is closed, remove it from client_sockets
                        del self.client_sockets[bot_id]
                        logging.error(f"Socket for bot_id {bot_id} was closed")
                    else:
                        # Some other OSError occurred, re-raise it
                        raise
            else:
                logging.error(f"No client connection found for bot_id {bot_id}")

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
            python_path = self.config['Manager']['pythonpath'] # Launch the bot using the local venv python so our packages are available to it
            command = [python_path] + [f"{bot_config['type']}.py", "--bot_id", bot_id]

            # Start the bot process
            print("DEBUG PATH: " + ' '.join(command))
            bot_process = subprocess.Popen(command)
            self.bot_processes[bot_id] = bot_process
            logging.info(f"Started bot {bot_id}")
        except Exception as e:
            logging.error(f"Failed to start bot {bot_id}: {e}")

    def stop_bot(self, bot_id, timeout=5):
        """Stop a bot process."""
        with self.client_sockets_lock:  # Acquire the lock before accessing client_sockets
            if bot_id in self.client_sockets:
                try:
                    self.send_message(bot_id, json.dumps({"command": "stop"}))
                except OSError as e:
                    if e.winerror == 10038:
                        del self.client_sockets[bot_id] # The socket is closed, remove it from client_sockets
                        logging.error(f"Socket for bot_id {bot_id} was closed")
                    else:
                        raise # Some other OSError occurred, re-raise it
            else:
                logging.error(f"No client connection found for bot_id {bot_id}")

        if bot_id not in self.bot_processes or self.bot_processes[bot_id].poll() is not None:
            logging.error(f"Bot {bot_id} is not running.")
            return

        try:
            # Wait for the bot process to terminate
            self.bot_processes[bot_id].wait(timeout)
        except subprocess.TimeoutExpired:
            # If the process does not terminate within the timeout, kill it
            self.bot_processes[bot_id].kill()
            self.bot_processes[bot_id].wait()  # Wait for the process to terminate

        del self.bot_processes[bot_id]  # Remove the bot from the bot_processes dictionary
        logging.info(f"Stopped bot {bot_id}")

    def shutdown(self):
        """Shutdown the manager. Stop all bots if the stop_bots_on_shutdown configuration option is set."""
        logging.info("Shutting down the manager.")
        self.shuttingdown = True
        if self.config.get("Manager", {}).get("stop_bots_on_shutdown", False):
            for bot_id in self.bot_processes.keys():
                self.stop_bot(bot_id)
        self.root.destroy()

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
