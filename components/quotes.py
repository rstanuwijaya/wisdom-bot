import requests
import io
import textwrap
import os
import pymongo
from dotenv import load_dotenv


from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw 

import discord
from discord.ext import commands
from dotenv import load_dotenv
from pilmoji import Pilmoji

# connect to mongodb
MONGO_URI = os.getenv('MONGODB_URI')
mongo_conn_str = f"mongodb+srv://{MONGO_URI}/myFirstDatabase?retryWrites=true&w=majority"
client = pymongo.MongoClient(mongo_conn_str)
db_quotes = client['quotes']
collections_images = db_quotes['image']

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
