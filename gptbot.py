import argparse
import logging
import discord
from discord.ext import commands
from botbase import BotBase


class GPTBot(BotBase):
    """
    A subclass of Bot that implements ChatGPT bot specific commands.
    """

    def __init__(self, token_env_var, log_file):
        super().__init__(token_env_var, log_file)
        logging.info("Bot initialized.")

    @commands.command()
    async def chat(self, ctx, *, message):
        """
        Respond with a message generated by ChatGPT.
        """
        response = self.generate_response(message)
        await ctx.send(response)

    def generate_response(self, message):
        """
        Generate a response using ChatGPT.
        """
        # This is a placeholder. Replace this with code to generate a response using ChatGPT.
        return f"ChatGPT says: {message}"

    def initialize_bot_commands(self):
        """
        Initialize the bot commands.
        """
        super().initialize_bot_commands()
        self.bot.add_command(self.chat)

    async def on_ready(self):
        print(f"{self.__class__.__name__} has connected to Discord!")

    def process_message(self, message):
        """
        Process a message received from the manager.
        """
        super().process_message(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a GPTBot.")
    parser.add_argument(
        "--token-env-var",
        help="The name of the environment variable that stores the bot token.",
    )
    parser.add_argument("--log", help="The file to log output to.")
    args = parser.parse_args()

    bot = GPTBot(token_env_var=args.token_env_var, log_file=args.log)
    bot.run()
