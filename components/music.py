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
    def __init__(self, id, title, url, requester=None, duration=None, thumbnail=None):
        self.id = id
        self.title = title
        self.url = url
        self.requester = requester
        self.duration = duration
        self.thumbnail = thumbnail

class VoiceState:
    def __init__(self, bot):
        self.bot = bot
        self.player = None
        self.text_channel = None
        self.voice_client = None
        self.queue: list[VoiceEntry] = []
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
        video_id = data.get("id")
        video_title = data.get("title")
        video_thumbnail = data.get("thumbnail")
        video_url = data.get("webpage_url")
        video_duration = data.get("duration")
        entry = VoiceEntry(video_id, video_title, video_url, requester=requester, duration=video_duration, thumbnail=video_thumbnail)
        self.queue.append(entry)
        return video_title, video_duration

    def pop(self, index):
        """pop at the specified index"""
        if index == 0: return None #should not edit the first element
        try:
            entry = self.queue.pop(index)
        except IndexError as exc:
            raise exc
        return entry

    def insert(self, index, entry):
        """insert after the specified index"""
        self.queue.insert(index, entry)
        return True

    def get_display_queue(self):
        """get formatted string of queue"""
        formatted_string = ""
        formatted_string += f"Now Playing: {self.queue[0].title}, Requested by {self.queue[0].requester}\n\n"
        for i in range(1, len(self.queue)):
            formatted_string += f"{i}. {self.queue[i].title}, Requested by {self.queue[i].requester}\n"
        return formatted_string

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

    @commands.command(aliases=['p'])
    async def play(self, ctx: commands.Context, *, query):
        """Add song into queue"""
        voice_state = self.get_voice_state(ctx.guild.id)
        if not ctx.voice_client.is_playing():        
            voice_state.queue = []
            title, duration = await voice_state.enqueue(ctx, query)
            await voice_state.start(ctx)
        else:
            title, duration = await voice_state.enqueue(ctx, query)
        await ctx.send(f'Adding to queue: {title}\nDuration: {duration//60}m{duration%60}s')

    @commands.command(aliases=['fs'])
    async def skip(self, ctx: commands.Context):
        """Skip the current song"""
        voice_state = self.get_voice_state(ctx.guild.id)
        if not ctx.voice_client.is_playing():        
            voice_state.queue = []
        await voice_state.skip()
        await ctx.send('Skipping!')

    @commands.command(aliases=['v'])
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

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        """Show the current queue"""
        voice_state = self.get_voice_state(ctx.guild.id)
        formatted_string = voice_state.get_display_queue()
        await ctx.send(formatted_string)

    @commands.command(aliases=['mv'])
    async def move(self, ctx, *args):
        """Move song queue"""
        voice_state = self.get_voice_state(ctx.guild.id)
        try:
            if len(args) < 1:
                args = (-1, 1)
            elif len(args) < 2:
                args = (int(args[0]), 1)
            else:
                args = (int(args[0]), int(args[1]))
        except ValueError as exc:
            await ctx.send(f'Wrong arguments')
            raise exc
        removed_elem = voice_state.pop(args[0])
        if not removed_elem: 
            await ctx.send(f'Index not found')
            return
        voice_state.insert(args[1], removed_elem)
        await ctx.send(f'Moved removed_elem{removed_elem.title} from #{args[0]} to #{args[1]}')

    @commands.command(aliases=['rm'])
    async def remove(self, ctx, *args):
        """Remove song queue"""
        try:
            if len(args) < 1:
                args = (-1,)
            else:
                args = (int(args[0]),)
        except ValueError as exc:
            await ctx.send(f'Wrong arguments')
            raise exc
        voice_state = self.get_voice_state(ctx.guild.id)
        removed_elem = voice_state.pop(args[0])
        if not removed_elem: 
            await ctx.send(f'Index not found')
            return
        await ctx.send(f'Removed {removed_elem.title}')

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
