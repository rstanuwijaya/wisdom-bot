import os
import uuid
import glob
import time
import io
import pathlib
import json

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

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(help='Warmest welcome message')
# @commands.has_role('not geh')
async def hello(ctx, *args):
    msg = 'Salam kenal, jancok kalian semua'

    await ctx.send(f'{msg} {", ".join(args)}')

@bot.command()
async def quotes(ctx, *args):
    if len(args) < 2:
        await ctx.send("Usage: quotes [background] \"[quotes_text]\" ")
    else:
        config_handler = open(os.path.join("assets_bg", args[0], "config.json"))
        config = json.load(config_handler) 
        img = Image.open(os.path.join("assets_bg", args[0], "image.png"))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("fonts/SansSerif.ttf", config['font_size'])
        draw.text((config['x'], config['y']), args[1] ,(255,255,255),font=font)
        config_handler.close()
        with io.BytesIO() as image_binary:
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            await ctx.send(file=discord.File(fp=image_binary, filename='image.png'))

bot.run(TOKEN)
