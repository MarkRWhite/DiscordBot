import argparse
import discord
from discord.ext import commands
from botbase import BotBase

class TestBot(BotBase):
    """
    A subclass of BotBase that implements TestBot specific commands.
    """
    def __init__(self, token_env_var, log_file):
        super().__init__(token_env_var, log_file)

    @commands.command()
    async def echo(self, ctx, *, message):
        """
        Respond with the same message that was received.
        """
        await ctx.send(message)

    def initialize_bot_commands(self):
        """
        Initialize the bot commands.
        """
        super().initialize_bot_commands()
        self.bot.add_command(self.echo)

    async def on_ready(self):
        print(f'{self.__class__.__name__} has connected to Discord!')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run a TestBot.')
    parser.add_argument('--token-env-var', help='The name of the environment variable that stores the bot token.')
    parser.add_argument('--log', help='The file to log output to.')
    args = parser.parse_args()

    bot = TestBot(token_env_var=args.token_env_var, log_file=args.log)
    bot.run()