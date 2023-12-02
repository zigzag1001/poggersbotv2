import os
import re
import time
import urllib
import yt_dlp
import asyncio
import random
import sqlite3
from dotenv import load_dotenv
from youtubesearchpython import SearchVideos

import discord
from discord.ext import commands, tasks
from discord.utils import get

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["r; ", "r;"], intents=intents)

# Configs

ytdlp_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

ffmpeg_opts = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

db_name = "db/bot.db"

# Database

mydb = sqlite3.connect(db_name)
mycursor = mydb.cursor()

# playlist
mycursor.execute("DROP TABLE IF EXISTS playlist")
mycursor.execute(
    "CREATE TABLE IF NOT EXISTS playlist (id INTEGER, guild INTEGER, url TEXT)"
)

# bot control
mycursor.execute("DROP TABLE IF EXISTS bot_control")
mycursor.execute(
    "CREATE TABLE IF NOT EXISTS bot_control (guild INTEGER, action TEXT, voice_channel INTEGER)"
)

# yt data
mycursor.execute("CREATE TABLE IF NOT EXISTS yt_data (url TEXT UNIQUE, name TEXT, duration TEXT)")

# Commit the changes and close the connection
mydb.commit()
mydb.close()


ytdl = yt_dlp.YoutubeDL(ytdlp_format_options)


# Functions
def is_connected(ctx):
    voice_client = ctx.message.guild.voice_client
    return voice_client and voice_client.is_connected()


def is_playing(ctx):
    voice_client = ctx.message.guild.voice_client
    return voice_client and voice_client.is_playing()


def is_user_connected(ctx):
    if ctx.message.author.voice:
        return True
    else:
        return False


def is_looping(ctx):
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT action FROM bot_control WHERE guild = ?", (ctx.guild.id,)
    )
    action = mycursor.fetchone()
    mydb.close()
    if action is None:
        return False
    elif action[0] == "loop":
        print("looping is true")
        return True
    else:
        return False


# Adds to playlist database, but with my id method
def add_to_playlist(ctx, url):
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT id FROM playlist WHERE guild = ? ORDER BY id DESC LIMIT 1",
        (ctx.guild.id,),
    )
    id = mycursor.fetchone()
    if id is None:
        id = 1
    else:
        id = id[0] + 1

    mycursor.execute(
        "INSERT INTO playlist (id, guild, url) VALUES (?, ?, ?)",
        (id, ctx.guild.id, url),
    )
    mydb.commit()
    mydb.close()


# Gets yt data, if not cached, gets from yt and caches
def get_yt_data(urls_list):
    if len(urls_list) == 0:
        return {}

    # pulls data from database into a dict
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url, name, duration FROM yt_data WHERE url IN ({})".format(
            ",".join(["?"] * len(urls_list))
        ),
        urls_list,
    )
    result = mycursor.fetchall()
    resultsdict = {}
    if result is not None:
        for x in result:
            resultsdict[x[0]] = (x[1], x[2])

    urls_list_data = {}

    # checks if data is in database, if not, gets from yt and caches into db
    for url in urls_list:
        if url in resultsdict:
            urls_list_data[url] = resultsdict[url]
        else:
            response = urllib.request.urlopen(url)
            html = response.read().decode()
            name = re.search(r"<title>(.*?)</title>", html).group(1).split(" - YouTube")[0]
            duration = re.search(r'"lengthSeconds":"(.*?)"', html)
            if duration is None:
                duration = 0
            else:
                duration = duration.group(1)
            if int(duration) >= 3600:
                mins = str(int(duration) // 3600) + ":" + str(int(duration) % 3600 // 60)
                secs = f"{int(duration) % 3600 % 60 : 03d}"
            else:
                mins = str(int(duration) // 60)
                secs = f"{int(duration) % 60 : 03d}"
            duration_minsec = f"{mins}:{secs.strip()}"
            try:
                mycursor.execute(
                    "INSERT INTO yt_data (url, name, duration) VALUES (?, ?, ?)",
                    (url, name, duration_minsec),
                )
                mydb.commit()
            except sqlite3.IntegrityError:
                pass
            urls_list_data[url] = (name, duration_minsec)
    mydb.close()
    return urls_list_data


# Actually traverses the queue and plays audio
# Also checks for bot control actions from db
async def play_audio(ctx, ytplaylist=[]):
    playlist = []
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
    )
    for x in mycursor:
        playlist.append(x[0])
    mydb.close()

    while playlist != []:
        if not is_connected(ctx): 
            await web(ctx, "Web interface: ")
            await ctx.author.voice.channel.connect()
        voice_client = ctx.message.guild.voice_client
        voice_channel = ctx.message.guild.voice_client.channel

        url = playlist.pop(0)

        try:
            time1 = time.time()  # For debugging

            info = ytdl.extract_info(url, download=False)
            for format in info["formats"]:
                if format["format_id"] == "251":
                    pureurl = format["url"]
                    break

            print(f"Url retrieve time taken: {time.time() - time1}")  # For debugging

            source = discord.FFmpegPCMAudio(pureurl, **ffmpeg_opts)
            source.read()
            voice_client.play(source)
            print(f"Playing {url}")
            while voice_client.is_playing():
                mydb = sqlite3.connect(db_name)
                mycursor = mydb.cursor()
                if voice_channel != ctx.message.guild.voice_client.channel:
                    print("Bot moved")
                    voice_client.pause()
                # Checks for bot control actions
                mycursor.execute(
                    "SELECT action FROM bot_control WHERE guild = ?", (ctx.guild.id,)
                )
                action = mycursor.fetchone()
                mydb.close()
                if action is not None:
                    mydb = sqlite3.connect(db_name)
                    mycursor = mydb.cursor()
                    if action[0] == "skip":
                        print("Skipping...")
                        voice_client.stop()
                        mycursor.execute(
                            "DELETE FROM bot_control WHERE guild = ? AND action = ?",
                            (ctx.guild.id, "skip"),
                        )
                        mydb.commit()
                        mydb.close()
                    elif action[0] == "playpause":
                        mycursor.execute(
                            "DELETE FROM bot_control WHERE guild = ? AND action = ?",
                            (ctx.guild.id, "playpause"),
                        )
                        mydb.commit()
                        if is_playing(ctx):
                            voice_client.pause()
                            paused = True
                        while paused:
                            mydb = sqlite3.connect(db_name)
                            mycursor = mydb.cursor()
                            mycursor.execute(
                                "SELECT action FROM bot_control WHERE guild = ? AND action = ?",
                                (ctx.guild.id, "playpause"),
                            )
                            action = mycursor.fetchone()
                            if action is None:
                                await asyncio.sleep(1)
                            else:
                                mycursor.execute(
                                    "DELETE FROM bot_control WHERE guild = ? AND action = ?",
                                    (ctx.guild.id, "playpause"),
                                )
                                mydb.commit()
                                paused = False
                        mydb.close()
                        voice_client.resume()
                await asyncio.sleep(1)
            voice_client.stop()
        except Exception as e:
            print(e)
            await ctx.send("Error playing audio, skipping...")
        mydb = sqlite3.connect(db_name)
        mycursor = mydb.cursor()
        if not is_looping(ctx):
            mycursor.execute(
                "DELETE FROM playlist WHERE url = ? AND guild = ? ORDER BY id LIMIT 1",
                (url, ctx.guild.id),
            )
            mydb.commit()

        playlist = []
        mycursor.execute(
            "SELECT url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
        )
        for x in mycursor:
            playlist.append(x[0])
        mydb.close()
        if not play_if_not_playing.is_running():
            play_if_not_playing.start(ctx)


# Events
@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    await bot.change_presence(activity=discord.Game(name="r;help"))


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith("r;"):
        await bot.process_commands(message)


# Properly handles empty voice channel and forced disconnects
@bot.event
async def on_voice_state_update(member, before, after):
    bot_voice_channel = member.guild.voice_client
    if bot_voice_channel is None:
        return
    if bot_voice_channel.channel.members == [bot.user]:
        await stop(None, member.guild)
        return
    # if bot is disconnected from voice channel
    if member == bot.user and not member in bot_voice_channel.channel.members:
        print("Bot disconnected")
        await stop(None, member.guild)
        return


# if playlist not empty, play audio, check every 5 seconds
@tasks.loop(seconds=5)
async def play_if_not_playing(ctx):
    if is_playing(ctx):
        return
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
    )
    playlist = []
    for x in mycursor:
        playlist.append(x[0])
    mydb.close()
    if playlist != [] and is_connected(ctx):
        await play_audio(ctx)

# Commands
@bot.command(
    name="play",
    help="Adds a song to queue, can be url or search term",
    aliases=["p", "search"],
)
async def play(ctx, *, search: str = None):
    ytplaylist = []
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if search is None:
        await skip(ctx)
        if not is_playing(ctx):
            await play_audio(ctx)
        return

    # Check if search is a url using regex
    protocol = r"(https:\/\/www\.|http:\/\/www\.|https:\/\/|http:\/\/)?"
    domain = r"[a-zA-Z]{2,}(\.[a-zA-Z]{2,})(\.[a-zA-Z]{2,})?"
    path = r"\/[a-zA-Z0-9]{2,}"
    subdomain = r"((https:\/\/www\.|http:\/\/www\.|https:\/\/|http:\/\/)?[a-zA-Z]{2,}(\.[a-zA-Z]{2,})(\.[a-zA-Z]{2,})?)"
    ip_domain = r"(https:\/\/www\.|http:\/\/www\.|https:\/\/|http:\/\/)?[a-zA-Z0-9]{2,}\.[a-zA-Z0-9]{2,}\.[a-zA-Z0-9]{2,}(\.[a-zA-Z0-9]{2,})?"

    msg = await ctx.send("Adding to queue...")
    final_regex = re.compile(f"{protocol}({domain}{path}|{subdomain}|{ip_domain})")
    plist = False
    # If search is a url
    if re.match(final_regex, search):
        # If search is a playlist url
        if "playlist?list=" in search:
            plist = True
            await ctx.message.add_reaction("➕")
            msgtext = "Adding playlist to queue...\n"
            await msg.edit(content=msgtext + "(yt-dlp query)")
            ytplaylist = (
                str(os.popen(f"yt-dlp {search} --flat-playlist --get-url").read())
                .strip()
                .split("\n")
            )
            await msg.edit(
                content=f"Added {len(ytplaylist)} songs to queue...\n(Adding to playlist database)"
            )
            yturl = ytplaylist[0]
            name = 'playlist'
            for x in ytplaylist:
                add_to_playlist(ctx, x)
        # If search is a video url
        else:
            yturl = search
            name = get_yt_data([yturl])[yturl][0]
        await msg.edit(content="Added to queue...")
    # If search is a search term
    else:
        await ctx.message.add_reaction("🔎")
        search = SearchVideos(search, offset=1, mode="json", max_results=5)
        info = search.result()
        info = eval(info)
        msgtext = ""
        resultnum = -1
        smsg = await ctx.send(content="Searching...")
        for x in range(5):
            msgtext += f'{x+1}. {info["search_result"][x]["title"]}\n'
        await smsg.edit(content=msgtext)
        for x in range(5):
            await smsg.add_reaction(f"{x+1}\N{combining enclosing keycap}")
        await smsg.add_reaction("❌")
        for i in range(10):
            # get next message, if its a number 1-5, set resultnum
            channel = ctx.channel
            last_message = await channel.fetch_message(channel.last_message_id)
            if last_message.content in ["1", "2", "3", "4", "5"] and last_message.author != bot.user:
                resultnum = int(last_message.content) - 1
                await last_message.add_reaction("👍")
                await smsg.delete()
                break
            reacts = get(bot.cached_messages, id=smsg.id).reactions
            for x in range(6):
                if reacts[x].count > 1:
                    resultnum = x
                    await smsg.delete()
                    break
            if resultnum != -1:
                break
            await asyncio.sleep(1)
        if resultnum == -1:
            await smsg.delete()
            resultnum = 0
        if resultnum == 5:
            await msg.edit(content="Cancelled")
            return
        yturl = info["search_result"][resultnum]["link"]
        name = info["search_result"][resultnum]["title"]

    await msg.edit(content = f"Added {name} to queue")
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT id, url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
    )
    result = mycursor.fetchall()
    addnext = False
    if len(result) > 9 and plist == False:
        qmsg = await ctx.send(
            "Queue is over 10 songs, do you want to place this song at the top of the queue?"
        )
        await qmsg.add_reaction("✅")
        await qmsg.add_reaction("❌")
        for i in range(5):
            reacts = get(bot.cached_messages, id=qmsg.id).reactions
            if reacts[0].count > 1:
                addnext = True
                secondid = result[1][0]
                mycursor.execute(
                    "UPDATE playlist SET id = id + 1 WHERE id >= ? AND guild = ?",
                    (secondid, ctx.guild.id),
                )
                mycursor.execute(
                    "INSERT INTO playlist (id, url, guild) VALUES (?, ?, ?)",
                    (secondid, yturl, ctx.guild.id),
                )
                mydb.commit()
                break
            elif reacts[1].count > 1:
                break
            await asyncio.sleep(1)
        await qmsg.delete()
    if addnext is False:
        add_to_playlist(ctx, yturl)
    await ctx.message.add_reaction("👍")
    mydb.close()
    if not is_playing(ctx):
        await play_audio(ctx, ytplaylist)


@bot.command(name="stop", help="Stops playing audio, clear queue and disconnects bot")
async def stop(ctx, guild=None):
    if ctx is not None:
        if not is_user_connected(ctx):
            await ctx.send("You are not connected to a voice channel")
            return
        if not is_connected(ctx):
            await ctx.send("I am not connected to a voice channel")
            return
        guild = ctx.guild
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute("DELETE FROM playlist WHERE guild = ?", (guild.id,))
    mydb.commit()
    mydb.close()
    voice_client = guild.voice_client
    await voice_client.disconnect()
    if play_if_not_playing.is_running():
        play_if_not_playing.cancel()


@bot.command(name="clear", help="Clears the queue", aliases=["c"])
async def clear(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute("DELETE FROM playlist WHERE guild = ?", (ctx.guild.id,))
    mydb.commit()
    mydb.close()
    await ctx.message.add_reaction("👍")


@bot.command(name="skip", help="Skips current song", aliases=["next", "s"])
async def skip(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    voice_client = ctx.message.guild.voice_client
    # skips by stopping current audio, play_audio will handle the rest
    voice_client.stop()
    await ctx.message.add_reaction("👍")


@bot.command(name="queue", help="Shows the current queue", aliases=["q"])
async def queue(ctx, num: int = 10):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    time1 = time.time()  # For debugging
    await ctx.message.add_reaction("👍")
    playlist = []
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id",
        (ctx.guild.id,),
    )
    for x in mycursor:
        playlist.append(x[0])
    mydb.close()
    if playlist == []:
        await ctx.send("The queue is empty")
        return
    extra = ""
    if len(playlist) > num:
        todisplay = num
        extra = f"\n {' '*10} + {len(playlist) - num} more, {len(playlist)} total"
    else:
        todisplay = len(playlist)
    msgtext = "```markdown\n" # markdown looks nicer than plain
    yt_data = get_yt_data(playlist[:todisplay])
    for x in range(todisplay):
        title = yt_data[playlist[x]][0]
        duration_minsec = yt_data[playlist[x]][1]
        msgtext += f"{x+1}. {title} -- {duration_minsec}\n"
    print(f"Queue time taken: {time.time() - time1}")  # For debugging
    fullmsg = msgtext + extra
    # Discord has a 2000 character limit, so if the queue is longer than that, split it into parts
    if len(fullmsg) >= 2000:
        partmsg = '```markdown\n'
        for x in range(todisplay):
            title = yt_data[playlist[x]][0]
            duration_minsec = yt_data[playlist[x]][1]
            partmsg += f"{x+1}. {title} -- {duration_minsec}\n"
            if len(partmsg) >= 1900:
                await ctx.send(partmsg + '```')
                partmsg = ''
        await ctx.send(partmsg + extra + '```')
    else:
        await ctx.send(fullmsg + "```")


@bot.command(name="shuffle", help="Shuffles the queue or provided playlist", aliases=["sh"])
async def shuffle(ctx, ytpurl=None):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    msg = await ctx.send("Shuffling...")
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id LIMIT 1", (ctx.guild.id,)
    )
    currenturl = mycursor.fetchone()
    # If a playlist url is provided, shuffle and add to queue
    if ytpurl is not None:
        await ctx.message.add_reaction("➕")
        await msg.edit(content="Adding playlist to queue...\n(yt-dlp query)")
        ytplaylist = (
            str(os.popen(f"yt-dlp {ytpurl} --flat-playlist --get-url").read())
            .strip()
            .split("\n")
        )
        await msg.edit(
            content=f"Added {len(ytplaylist)} songs to queue...\n(Adding to playlist database)"
        )
        if currenturl is None:
            currenturl = ytplaylist.pop(random.randint(0, len(ytplaylist) - 1))
            ytplaylist.insert(0, currenturl)
        for x in ytplaylist:
            add_to_playlist(ctx, x)
        await msg.edit(content="Added to database...\n(Shuffling)")
    if currenturl is None:
        await ctx.send("The queue is empty")
        return
    mycursor.execute(
        f"SELECT id, url FROM playlist WHERE guild = {ctx.guild.id} ORDER BY id"
    )
    result = mycursor.fetchall()
    ids = []
    urls = []
    for x in result:
        ids.append(x[0])
        urls.append(x[1])
    currentid = ids.pop(0)
    currenturl = urls.pop(0)
    random.shuffle(ids)
    for i in range(len(ids)):
        mycursor.execute(f"UPDATE playlist SET id = {ids[i]} WHERE url = '{urls[i]}' AND guild = {ctx.guild.id}")
        mydb.commit()
    mydb.close()
    await ctx.message.add_reaction("👍")
    await msg.edit(content="Shuffled...\n(Loading titles for queue)")
    await queue(ctx)
    await msg.delete()
    if not is_playing(ctx) and ytpurl is not None:
        await play_audio(ctx)


@bot.command(name="loop", help="Loops the current song", aliases=["l"])
async def loop(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    if is_looping(ctx):
        mycursor.execute(
            "DELETE FROM bot_control WHERE guild = ? AND action = ?",
            (ctx.guild.id, "loop"),
        )
        await ctx.send("Stopped looping")
    else:
        mycursor.execute(
            "INSERT INTO bot_control (guild, action) VALUES (?, ?)",
            (ctx.guild.id, "loop"),
        )
        await ctx.send("Looping current song")
    await ctx.message.add_reaction("👍")
    mydb.commit()
    mydb.close()


@bot.command(name="pause", help="Pauses/unpauses the bot", aliases=["resume", "unpause"])
async def pause(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "INSERT INTO bot_control (guild, action) VALUES (?, ?)",
        (ctx.guild.id, "playpause"),
    )
    mydb.commit()
    mydb.close()
    await ctx.message.add_reaction("👍")
    if not is_playing(ctx):
        await play_audio(ctx)


@bot.command(name="web", help="Shows the web interface link", aliases=["website", "w"])
async def web(ctx, msg=''):
    baseurl = os.getenv("BASE_URL").strip("/")
    await ctx.send(msg + baseurl + "/?guild=" + str(ctx.guild.id))


@bot.command(name="join", help="Joins the voice channel", aliases=["j"])
async def join(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    await ctx.message.add_reaction("👍")
    if not is_connected(ctx):
        await ctx.author.voice.channel.connect()
        if not play_if_not_playing.is_running():
            play_if_not_playing.start(ctx)
    if not is_playing(ctx):
        await play_audio(ctx)

bot.run(TOKEN)
