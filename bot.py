import collections
import os
import uuid
import glob
import time
import io
import pathlib
import json
import requests
import pymongo

import discord
from discord.ext import commands
from dotenv import load_dotenv

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw 

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
# @commands.has_role('not geh')
async def hello(ctx, *args):
    msg = 'Salam kenal, jancok kalian semua'
    await ctx.send(f'{msg} {", ".join(args)}')

@bot.command()
async def quote(ctx, *args):
    if len(args) < 2:
        await ctx.send("Usage: quotes [background] \"[quotes_text]\" ")
    else:
        name = args[0]
        config = collections_images.find_one({"name": name})
        if config is None: 
            await ctx.send("Image template not found")
            return
        response = requests.get(config['image_url'])
        img = Image.open(io.BytesIO(response.content))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("fonts/SansSerif.ttf", config['font_size'])
        draw.text((config['x'], config['y']), args[1] ,(255,255,255),font=font)
        with io.BytesIO() as image_binary:
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            await ctx.send(file=discord.File(fp=image_binary, filename='image.png'))

bot.run(TOKEN)
