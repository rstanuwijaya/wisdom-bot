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

import youtube_dl
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix='>')

print("Starting Bot")

mongo_uri = os.getenv('MONGODB_URI')
mongo_conn_str = f"mongodb+srv://{mongo_uri}/myFirstDatabase?retryWrites=true&w=majority"
client = pymongo.MongoClient(mongo_conn_str)
db_quotes = client['quotes']
collections_images = db_quotes['image']

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)



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



bot.run(TOKEN)
