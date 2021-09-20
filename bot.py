import os

from discord.ext import commands
from dotenv import load_dotenv

import components

def main():
    print("Starting Bot")
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    bot.run(TOKEN)

bot = commands.Bot(command_prefix='>')

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(help='Warmest welcome message')
async def hello(ctx, *args):
    msg = 'Salam kenal, jancok kalian semua'
    await ctx.send(f'{msg} {", ".join(args)}')

@bot.command(help='Usage: quotes [background] \"[quotes_text]\" ')
async def quote(ctx, *args):
    components.quote(ctx, *args)

@bot.command(help='Usage: play [title/url]')
async def play(ctx, *args):
    await ctx.send(f'Not active yet')

if __name__ == '__main__':
    main()
