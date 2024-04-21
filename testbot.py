import argparse
import logging
import discord
from discord.ext import commands
from botbase import BotBase


class TestBot(BotBase):
    """
    A subclass of BotBase that implements TestBot specific commands.
    """

    def __init__(self, bot_id=None):
        super().__init__(bot_id)
        logging.info("Bot initialized.")

    @commands.command()
    async def echo(self, ctx, *, message=None):
        """
        Respond with the same message that was received.
        """
        await ctx.send(message)

    def initialize_bot_commands(self):
        """
        Initialize the bot commands.
        """
        super().initialize_bot_commands()

    async def on_ready(self):
        logging.info(f"{self.__class__.__name__} has connected to Discord!")

    def shutdown(self):
        """
        Shutdown the bot.
        """
        super().shutdown()

    def process_message(self, message):
        """
        Process a message received from the manager.
        """
        super().process_message(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a TestBot.")
    parser.add_argument( "--bot_id", help="The bot ID.")
    args = parser.parse_args()

    bot = TestBot(bot_id=args.bot_id)
    bot.run()
