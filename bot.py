import os

from discord.ext import commands
from dotenv import load_dotenv

import components

bot = commands.Bot(command_prefix='>')
bot.add_cog(components.Quote(bot))
bot.add_cog(components.Music(bot))

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(help='Warmest welcome message')
async def hello(ctx, *args):
    msg = 'Salam kenal, jancok kalian semua'
    await ctx.send(f'{msg} {", ".join(args)}')

def main():
    print("Starting Bot")
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
