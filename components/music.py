from sys import excepthook
import time
from discord import channel
import youtube_dl
import asyncio
import discord
from discord.ext import commands
import lyricsgenius
from dotenv import load_dotenv

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

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, timestamp=0):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': f'-vn -ss {timestamp}'
        }
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class VoiceEntry:
    def __init__(self, query, id, title, url, channel=None, requester=None, duration=None, thumbnail=None):
        self.id = id
        self.title = title
        self.url = url
        self.requester = requester
        self.duration = duration
        self.thumbnail = thumbnail
        self.query = query
        self.channel = channel
        self.seek_timestamp = 0
        self.last_play_time = time.time()

    def __str__(self):
        return self.title

class VoiceState:
    def __init__(self, bot, text_channel=None):
        self.bot = bot
        self.player = None
        self.text_channel: discord.TextChannel = text_channel
        self.voice_client = None
        self.queue: list[VoiceEntry] = []
        self.play_next_song = asyncio.Event()
        self.loop = False
        self.queue_loop = False

    async def play(self, query, send=True, timestamp=0):
        self.player = await YTDLSource.from_url(query, loop=False, stream=True, timestamp=timestamp)
        entry = self.queue[0]
        if send: await self.send_now_playing()
        self.last_play_time = time.time()
        self.voice_client.play(self.player, after=self.after_finished)

    async def disconnect(self):
        self.voice_client.disconnect()

    async def clear(self):
        self.queue = [self.queue[0], ]

    async def stop(self):
        self.queue = []
        self.voice_client.stop()

    async def start(self, ctx):
        self.voice_client = ctx.voice_client
        await self.play(self.queue[0].url)

    async def next(self):
        if len(self.queue) == 0: return
        seek_timestamp = self.seek_timestamp
        if not self.loop and seek_timestamp == 0:
            popped = self.queue.pop(0)
            if self.queue_loop:
                self.queue.append(popped)
        self.seek_timestamp = 0
        if len(self.queue) == 0:
            await self.stop()
        else:
            await self.play(self.queue[0].url, send=not self.loop and seek_timestamp == 0, timestamp=seek_timestamp)

    async def skip(self):
        if self.loop:
            popped = self.queue.pop(0)
        self.voice_client.stop()

    async def seek(self, timestamp=0):
        self.seek_timestamp = timestamp
        self.voice_client.stop()

    async def enqueue(self, ctx, query):
        requester = ctx.message.author.display_name
        if query.startswith("https://youtu.be/"):
            data = ytdl.extract_info(f'{query}', download=False)
        else:
            data = ytdl.extract_info(f'ytsearch:{query}', download=False)
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        video_id = data.get("id")
        video_title = data.get("title")
        video_thumbnail = data.get("thumbnail")
        video_url = data.get("webpage_url")
        video_duration = data.get("duration")
        video_channel = data.get("channel")
        entry = VoiceEntry(query, video_id, video_title, video_url, channel=video_channel, requester=requester, duration=video_duration, thumbnail=video_thumbnail)
        self.queue.append(entry)
        return entry

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

    def length(self):
        """return the length of the queue"""
        return len(self.queue)

    def after_finished(self, exc=None):
        try:
            fut = asyncio.run_coroutine_threadsafe(self.next(), self.bot.loop)
            fut.result()
        except Exception as e:
            print(e)

    @staticmethod
    def get_formatted_duration(time):
        minutes = time//60
        seconds = time%60
        if seconds < 10:
            seconds = f'0{seconds}'
        formatted_string = f'{minutes}:{seconds}'
        return formatted_string
    
    @staticmethod
    def get_animated_elapsed_time(time, duration):
        percentage = time/duration
        formatted_string = ''
        length = 20
        for i in range(length):
            if i == int(percentage*length):
                formatted_string += 'o'
            else:
                formatted_string += '='
        return formatted_string

    def get_formatted_song(self, song):
        return f'[{song.title}]({song.url}) | `{self.get_formatted_duration(song.duration)} Requested by: {song.requester}`'

    def get_up_next(self, queue):
        formatted_string = ''
        if len(queue) <= 1:
            formatted_string += 'Empty'
        for i in range(1, len(queue)):
            formatted_string += f'`{i}.` {self.get_formatted_song(queue[i])}\n\n'
        return formatted_string
    
    async def send_now_playing(self, entry=None, elapsed_time=None):
        if entry is None:
            entry = self.queue[0]
        embed=discord.Embed(title=entry.title, url=entry.url, color=0xFFC0CB)
        embed.set_thumbnail(url=entry.thumbnail)
        embed.set_author(name="Now Playing")
        if elapsed_time is not None:
            embed.add_field(name="Time", value=self.get_animated_elapsed_time(elapsed_time, entry.duration), inline=False)
        embed.add_field(name="Channel", value=(entry.channel), inline=True)
        embed.add_field(name="Song Duration", value=self.get_formatted_duration(entry.duration), inline=True)
        await self.text_channel.send(embed=embed)

class Music(commands.Cog):
    def __init__(self, bot):
        load_dotenv()
        self.bot: commands.Bot = bot
        self.voice_states: dict[str, VoiceState] = dict()
        self.genius = lyricsgenius.Genius()

    def get_voice_state(self, guild_id, text_channel=None):
        if guild_id not in self.voice_states:
            self.voice_states[guild_id] = VoiceState(self.bot, text_channel=text_channel)
        return self.voice_states[guild_id]

    @commands.command(aliases=['p'])
    async def play(self, ctx: commands.Context, *, query):
        """Add song into queue. !p [query: text/youtube_url]"""
        voice_state = self.get_voice_state(ctx.guild.id, ctx.message.channel)
        await ctx.send(f':mag_right: **Searching** `{query}`')
        if not ctx.voice_client.is_playing() or voice_state.queue == []:        
            voice_state.queue = []
            entry = await voice_state.enqueue(ctx, query)
            await voice_state.start(ctx)
        else:
            entry = await voice_state.enqueue(ctx, query)
        embed=discord.Embed(title=entry.title, url=entry.url, color=0xFFC0CB)
        embed.set_thumbnail(url=entry.thumbnail)
        embed.set_author(name="Added to queue", icon_url=ctx.author.avatar_url)
        embed.add_field(name="Song Duration", value=voice_state.get_formatted_duration(entry.duration), inline=True)
        embed.add_field(name="Position", value=voice_state.length()-1 if voice_state.length()-1 > 0 else "Now Playing!", inline=True)
        if voice_state.length() > 1:
            await ctx.send(embed=embed)

    @commands.command(aliases=['fs'])
    async def skip(self, ctx: commands.Context):
        """Skip the current song. !fs"""
        voice_state = self.get_voice_state(ctx.guild.id)
        await voice_state.skip()
        await ctx.send('**:fast_forward: Skipped**')

    @commands.command(aliases=['v'])
    async def volume(self, ctx, volume: int):
        """Changes the player's volume. !v [volume]"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        if volume is None:
            volume = ctx.voice_client.source.volume
            await ctx.send(f"**Volume**: `{volume}`%")
        else:
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"**Volume**: `{volume}`%")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        voice_state = self.get_voice_state(ctx.guild.id)
        await voice_state.stop()
        await ctx.send("**Stopped!**")

    @commands.command(aliases=['np'])
    async def now_playing(self, ctx):
        """Show now playing. !q"""
        # await ctx.send("**JANCOK!**")
        voice_state = self.get_voice_state(ctx.guild.id)
        elapsed_time = (time.time() - voice_state.last_play_time)
        await voice_state.send_now_playing(elapsed_time=elapsed_time)

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        """Show the current queue. !q"""
        voice_state = self.get_voice_state(ctx.guild.id)
        queue = voice_state.queue
        if len(queue) == 0:
            await ctx.send("**Nothing in queue!**")
            return
        total_time = sum([entry.duration for entry in queue])
        embed=discord.Embed(title=f"Queue for {ctx.guild.name}", color=0xFFC0CB)
        embed.set_footer(text=f"Total Queue Time: {voice_state.get_formatted_duration(total_time)}", icon_url=ctx.author.avatar_url)
        embed.add_field(name="Now Playing", value=voice_state.get_formatted_song(queue[0]), inline=False)
        embed.add_field(name="Up Next", value=voice_state.get_up_next(queue), inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=['l'])
    async def lyrics(self, ctx, *, query=None):
        """Show the lyrics of current song. !l [query = current_song]"""
        voice_state = self.get_voice_state(ctx.guild.id)
        if not query:
            entry = voice_state.queue[0]
            song = self.genius.search_song(entry.query)
        else:
            song = self.genius.search_song(query)
        if song is None:
            await ctx.send("**Lyrics Not Found**")
            return
        def get_formatted_description(song):
            formatted_string = ""
            formatted_string += f'__Artist: {song.artist}__\n\n'
            formatted_string += f'__Lyrics:__ \n'
            formatted_string += f'{song.lyrics[:1024*2]}'
            return formatted_string
        embed=discord.Embed(title=song.full_title, description=get_formatted_description(song), color=0xFFC0CB)
        await ctx.send(embed=embed)

    @commands.command(aliases=['mv'])
    async def move(self, ctx, *args):
        """Move song in queue. !mv [origin = last] [target = first]"""
        voice_state = self.get_voice_state(ctx.guild.id)
        try:
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
            if removed_elem is None: 
                await ctx.send(f'**Index not found**')
                return
            voice_state.insert(args[1], removed_elem)
            await ctx.send(f'**Moved `{removed_elem.title}` from `#{args[0]}` to `#{args[1]}`**')
        except Exception as exc:
            await ctx.send(f'**Move Failed**')
            raise exc

    @commands.command()
    async def seek(self, ctx, *, args):
        voice_state = self.get_voice_state(ctx.guild.id)
        """Seek to a timestamp"""
        try:
            timestamp = args.split(':')
            timestamp_in_seconds = int(timestamp[0])*60 + int(timestamp[1])
            if timestamp_in_seconds < 0 or timestamp_in_seconds > voice_state.queue[0].duration:
                await ctx.send(f"**Invalid time!**")
                return
            await voice_state.seek(timestamp_in_seconds)
            await ctx.send(f"**Seeked to {args}**")
        except Exception as exc:
            await ctx.send(f'**Error!**')
        voice_state = self.get_voice_state(ctx.guild.id)

    @commands.command()
    async def loop(self, ctx):
        """Loop a single song"""
        voice_state = self.get_voice_state(ctx.guild.id)
        voice_state.loop = not voice_state.loop
        await ctx.send(f'**Loop: `{"ON" if voice_state.loop else "OFF"}`**')

    @commands.command(aliases=['ql'])
    async def queueloop(self, ctx):
        """Queue loop"""
        voice_state = self.get_voice_state(ctx.guild.id)
        voice_state.queue_loop = not voice_state.queue_loop
        await ctx.send(f'**Queue Loop: `{"ON" if voice_state.queue_loop else "OFF"}`**')

    @commands.command(aliases=['rm'])
    async def remove(self, ctx, *args):
        """Remove song from queue. !rm [index = last]"""
        try:
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
                await ctx.send(f'**Index not found**')
                return
            await ctx.send(f'**Removed `{removed_elem.title}`**')
        except Exception as exc:
            await ctx.send(f'**Remove Failed**')
            raise exc

    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx):
        """Disconnect form voice channel"""
        voice_state = self.get_voice_state(ctx.guild.id)
        voice_state.disconnect()
        await ctx.send(f'**Adios!**')

    @commands.command(aliases=['clc', 'clean'])
    async def clear(self, ctx):
        """Clear the queue"""
        voice_state = self.get_voice_state(ctx.guild.id)
        voice_state.clear()
        await ctx.send(f'**Cleared!**')

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                await ctx.send(f"**Joined** {ctx.author.voice.channel.name} **to bound to** `#{ctx.message.channel.name}`")
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
