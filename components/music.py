from re import A
import youtube_dl
import asyncio
import discord
from discord.ext import commands

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
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
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

class VoiceEntry:
    def __init__(self, title, url, requester=None):
        self.title = title
        self.url = url
        self.requester = requester

class VoiceState:
    def __init__(self, bot):
        self.bot = bot
        self.player = None
        self.text_channel = None
        self.voice_client = None
        self.queue = []
        self.play_next_song = asyncio.Event()

    async def play(self, query):
        self.player = await YTDLSource.from_url(query, loop=False, stream=True)
        self.voice_client.play(self.player, after=self.after_finished)

    async def stop(self):
        self.voice_client.stop()

    async def start(self, ctx):
        self.voice_client = ctx.voice_client
        await self.play(self.queue[0].url)

    async def next(self):
        self.queue.pop(0)
        if len(self.queue) == 0:
            await self.stop()
        else:
            await self.stop()
            await self.play(self.queue[0].url)

    async def skip(self):
        await self.next()

    async def enqueue(self, ctx, query):
        requester = ctx.message.author.display_name
        data = ytdl.extract_info(f'ytsearch:{query}', download=False)
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        title = data.get('title')
        url = data.get('webpage_url')
        entry = VoiceEntry(title, url, requester)
        self.queue.append(entry)
        return title

    def after_finished(self, exc=None):
        try:
            fut = asyncio.run_coroutine_threadsafe(self.next(), self.bot.loop)
            fut.result()
        except Exception as e:
            print(e)
        
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.voice_states: dict[str, VoiceState] = dict()

    def get_voice_state(self, guild_id):
        if guild_id not in self.voice_states:
            self.voice_states[guild_id] = VoiceState(self.bot)
        return self.voice_states[guild_id]

    @commands.command(pass_context=True)
    async def play(self, ctx: commands.Context, *, query):
        """Add song into queue"""
        voice_state = self.get_voice_state(ctx.guild.id)
        if not ctx.voice_client.is_playing():        
            voice_state.queue = []
            title = await voice_state.enqueue(ctx, query)
            await voice_state.start(ctx)
        else:
            title = await voice_state.enqueue(ctx, query)
        await ctx.send('Adding to queue: {}'.format(title))

    @commands.command(pass_context=True)
    async def skip(self, ctx: commands.Context):
        """Skip the current song"""
        voice_state = self.get_voice_state(ctx.guild.id)
        if not ctx.voice_client.is_playing():        
            voice_state.queue = []
        await voice_state.skip()
        await ctx.send('Skipping!')

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        voice_state = self.get_voice_state(ctx.guild.id)
        await voice_state.stop()

    @commands.command()
    async def queue(self, ctx):
        """Show the current queue"""
        voice_state = self.get_voice_state(ctx.guild.id)
        queue = voice_state.queue
        formatted_string = ""
        for i in range(len(queue)):
            formatted_string += f"{i+1}. {queue[i].title} Requested by {queue[i].requester}\n"
        await ctx.send(formatted_string)

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
