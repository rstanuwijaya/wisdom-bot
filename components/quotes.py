from discord.ext.commands import bot
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
load_dotenv()
mongo_uri = os.getenv('MONGODB_URI')
mongo_conn_str = f"mongodb+srv://{mongo_uri}/myFirstDatabase?retryWrites=true&w=majority"
client = pymongo.MongoClient(mongo_conn_str)
db_quotes = client['quotes']
collections_images = db_quotes['image']

class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.collections_images = collections_images

    @commands.command(pass_context=True)
    async def quote(self, ctx, *args):
        """Quote a meme. !quote [template] [text]"""
        message = " ".join(args[1:])
        print('quote', args[0], message)
        if len(args) < 2:
            await ctx.send("Usage: quotes [template] [text] ")
        else:
            name = args[0]
            config: dict = self.collections_images.find_one({"name": name})
            if config is None: 
                await ctx.send("Image template not found")
                return
            response = requests.get(config['image_url'])
            img = Image.open(io.BytesIO(response.content))
            font = ImageFont.truetype("fonts/" + config.get("font_family", "TimesNewRoman") + ".ttf", config['font_size'])
            quote = "\n".join(textwrap.wrap(message, width=config.get("width", 20)))
            with Pilmoji(img) as pilmoji:
                pilmoji.text((config['x'], config['y']), quote, (255,255,255), font)
            with io.BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)
                await ctx.send(file=discord.File(fp=image_binary, filename='image.png'))
