import os
import glob
import time
import io
import pathlib
import json
import requests
import pymongo
import textwrap

import discord
from discord.ext import commands
from dotenv import load_dotenv
from pilmoji import Pilmoji

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw 

from utils import *

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix='>')

print("Starting Bot")

mongo_uri = os.getenv('MONGODB_URI')
mongo_conn_str = f"mongodb+srv://{mongo_uri}/myFirstDatabase?retryWrites=true&w=majority"
client = pymongo.MongoClient(mongo_conn_str)
db_quotes = client['quotes']
collections_images = db_quotes['image']

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(help='Warmest welcome message')
async def hello(ctx, *args):
    msg = 'Salam kenal, jancok kalian semua'
    await ctx.send(f'{msg} {", ".join(args)}')

@bot.command(help='Usage: quotes [background] \"[quotes_text]\" ')
async def quote(ctx, *args):
    print('quote', args)
    if len(args) < 2:
        await ctx.send("Usage: quotes [background] \"[quotes_text]\" ")
    else:
        name = args[0]
        config: dict = collections_images.find_one({"name": name})
        if config is None: 
            await ctx.send("Image template not found")
            return
        response = requests.get(config['image_url'])
        img = Image.open(io.BytesIO(response.content))
        font = ImageFont.truetype("fonts/" + config.get("font_family", "TimesNewRoman") + ".ttf", config['font_size'])
        quote = "\n".join(textwrap.wrap(args[1], width=config.get("width", 20)))
        with Pilmoji(img) as pilmoji:
            pilmoji.text((config['x'], config['y']), quote, (255,255,255), font)
        with io.BytesIO() as image_binary:
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            await ctx.send(file=discord.File(fp=image_binary, filename='image.png'))

@bot.command()
async def play(ctx, *args):
    url = args[0]
    print('play', url)
    voice_channel = ctx.message.author.voice.channel

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=False, stream=True)
        voice_client = await voice_channel.connect()
        voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
    await ctx.send('Now playing: {}'.format(player.title))

if __name__ == '__main__':
    bot.run(TOKEN)
