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
from discord.ext import commands
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
mycursor.execute(
    "CREATE TABLE IF NOT EXISTS yt_data (url TEXT UNIQUE, name TEXT, duration TEXT)"
)

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
    mycursor.execute("SELECT action FROM bot_control WHERE guild = ?", (ctx.guild.id,))
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
def add_to_playlist(ctx, url="", arr=[]):
    # either url or arr, convert to arr
    if url == "" and arr == []:
        print("No url provided")
        return
    if arr == []:
        arr.append(url)
    elif arr != [] and url != "":
        arr.insert(0, url)

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

    # fills in database with id, guild, url
    arr = [(id + i, ctx.guild.id, x) for i, x in enumerate(arr)]

    mycursor.executemany(
        "INSERT INTO playlist (id, guild, url) VALUES (?, ?, ?)",
        arr,
    )
    mydb.commit()
    mydb.close()


# Gets yt data, if not cached, gets from yt and caches
# returns a dict of url: (name, duration)
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

    # puts cached data into dict for future reference
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
            # html extraction
            try:
                response = urllib.request.urlopen(url)
                html = response.read().decode()
            except urllib.error.HTTPError:
                print("HTTPError", url)
            if "youtu.be" in url or "youtube.com" in url:
                name = (
                    re.search(r"<title>(.*?)</title>", html).group(1).split(" - YouTube")[0]
                )
                try:
                    duration = re.search(r'"lengthSeconds":"(.*?)"', html).group(1)
                except AttributeError:
                    duration = None
            elif "soundcloud.com" in url:
                time1 = time.time()  # debug
                if "api-v2" in url:
                    print("api-v2")
                    data = os.popen(f"yt-dlp {url} --get-title --get-duration").read().strip().split("\n")
                    name = data[0]
                    duration = data[1]
                    min = int(duration.split(":")[0])
                    sec = int(duration.split(":")[1])
                    duration = str(min * 60 + sec)
                else:
                    print("not api-v2")
                    name = re.search(r'<meta property="og:title" content="(.*?)">', html).group(1)
                    try:
                        duration = re.search(r'<span aria-hidden="true">(\d+):(\d+)</span>', html)
                        mins = int(duration.group(1))
                        secs = int(duration.group(2))
                        duration = str(mins * 60 + secs)
                    except AttributeError:
                        duration = None
                print(f"Soundcloud name duration time taken: {time.time() - time1}")  # debug

            # duration calculation
            if duration is None:
                duration = 0
            if int(duration) >= 3600:
                mins = (
                    str(int(duration) // 3600) + ":" + str(int(duration) % 3600 // 60)
                )
                secs = f"{int(duration) % 3600 % 60 : 03d}"
            else:
                mins = str(int(duration) // 60)
                secs = f"{int(duration) % 60 : 03d}"
            duration_minsec = f"{mins}:{secs.strip()}"

            # add to database
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


async def add_url(ctx, url, msg=None):
    search = url
    plist = False
    vidplist = False
    yturl = ""
    name = ""
    if "youtu.be" in search or "youtube.com" in search:
        if "playlist?list=" in search:
            plist = True
            await ctx.message.add_reaction("➕")
            msgtext = "Adding playlist to queue...\n"
            await msg.edit(content=msgtext + "(yt-dlp query)")
            # TODO: make seperate function since same thing used in three places
            # cleans playlist url, just in case
            plistid = search.split("playlist?list=")[1][:34]
            plisturl = f"https://www.youtube.com/playlist?list={plistid}"
            ytplaylist = (
                str(os.popen(f"yt-dlp {plisturl} --flat-playlist --get-url").read())
                .strip()
                .split("\n")
            )
            await msg.edit(
                content=f"Added {len(ytplaylist)} songs to queue...\n(Adding to playlist database)"
            )
            yturl = ytplaylist[0]
            name = "playlist"
            add_to_playlist(ctx, arr=ytplaylist, url="")
        # If search is a video url
        else:
            yturl = search
            name = get_yt_data([yturl])[yturl][0]
            # video urls can have a playlist attached, so check for that
            if "&list=" in yturl:
                plistmsg = await ctx.send("Do you want to add the playlist to queue?")
                await plistmsg.add_reaction("✅")
                await plistmsg.add_reaction("❌")
                for i in range(5):
                    reacts = get(bot.cached_messages, id=plistmsg.id).reactions
                    if reacts[0].count > 1:
                        plist = True
                        vidplist = True
                        break
                    elif reacts[1].count > 1:
                        await plistmsg.delete()
                        break
                    await asyncio.sleep(1)
        await msg.edit(content="Added to queue...")
    elif "soundcloud.com" in search:
        search = search.split("?")[0]
        if "sets/" in search:
            plist = True
            await ctx.message.add_reaction("➕")
            msgtext = "Adding playlist to queue...\n"
            await msg.edit(content=msgtext + "(yt-dlp query)")
            scplaylist = (
                    str(os.popen(f"yt-dlp {search} --flat-playlist --get-url").read())
                    .strip()
                    .split("\n")
            )
            await msg.edit(
                    content=f"Added {len(scplaylist)} songs to queue...\n(Adding to playlist database)"
            )
            yturl = scplaylist[0]
            name = "playlist"
            add_to_playlist(ctx, arr=scplaylist, url="")
        else:
            yturl = search
            name = get_yt_data([yturl])[yturl][0]
    else:
        await ctx.send("url not supported yet, only youtube, soundcloud for now")
        return [None, None, None, None]
    return [plist, vidplist, yturl, name]



# Actually traverses the queue and plays audio
# Also checks for bot control actions from db
async def play_audio(ctx):
    if is_playing(ctx):
        print("Already playing, returning")  # debug
        return
    five_times = 0  # For checking if bot is inactive 5*120 = 10 minutes
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
    )
    playlist = [x[0] for x in mycursor]
    mydb.close()
    if not is_connected(ctx):
        await web(ctx, "Web interface: ")
        await ctx.author.voice.channel.connect()

    while is_connected(ctx):
        if is_playing(ctx):
            print("Already playing, returning (in loop)")  # debug
            return

        # Checks if bot is inactive and if songs have been added in web
        if playlist == [] and is_connected(ctx):
            five_times += 1
            if five_times == 120:
                await ctx.send("Inactive for 10 minutes, disconnecting...")
                await stop(ctx)
                return
            playlist = []
            mydb = sqlite3.connect(db_name)
            mycursor = mydb.cursor()
            mycursor.execute(
                "SELECT url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
            )
            playlist = [x[0] for x in mycursor]
            mydb.close()
            # if playlist is still empty, skip entire loop and wait 5 seconds
            if playlist == []:
                await asyncio.sleep(5)
                continue
        five_times = 0  # reset inactive counter if playing song

        # if bot is moved to another voice channel, update vars
        voice_client = ctx.message.guild.voice_client
        voice_channel = ctx.message.guild.voice_client.channel

        url = playlist.pop(0)

        try:
            time1 = time.time()  # debug

            # gets url of audio stream
            info = ytdl.extract_info(url, download=False)
            for format in info["formats"]:
                if format["format_id"] == "251" or format["format_id"] == "http_mp3_128":
                    pureurl = format["url"]
                    break

            print(f"Url retrieve time taken: {time.time() - time1}")  # debug

            source = discord.FFmpegPCMAudio(pureurl, **ffmpeg_opts)
            source.read()
            voice_client.play(source)
            print(f"Playing {url}")

            # main audio loop, also checks for bot control actions
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
                    # skpis by stopping current audio, loop goes on to next song
                    if action[0] == "skip":
                        print("Skipping...")
                        voice_client.stop()
                        mycursor.execute(
                            "DELETE FROM bot_control WHERE guild = ? AND action = ?",
                            (ctx.guild.id, "skip"),
                        )
                        mydb.commit()
                        mydb.close()
                    # pause by pausing audio, loop waits for same action to resume
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

        mycursor.execute(
            "SELECT url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
        )
        playlist = [x[0] for x in mycursor]
        mydb.close()


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
    # stop if bot is alone in voice channel
    if bot_voice_channel.channel.members == [bot.user]:
        await stop(None, member.guild)
        return
    # stop if bot is force disconnected from voice channel
    if member == bot.user and member not in bot_voice_channel.channel.members:
        print("Bot disconnected")
        await stop(None, member.guild)
        return


# Commands


# handles search and url adding to queue
# start play_audio if not already playing
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
    vidplist = False
    plist = False
    # If search is a url
    if re.match(final_regex, search):
        url_data = await add_url(ctx, search, msg)
        if url_data[0] is None:
            return
        plist = url_data[0]  # whether or not url is a playlist
        vidplist = url_data[1]  # whether or not url is a video with a playlist attached
        yturl = url_data[2]  # url of video
        name = url_data[3]  # name of video
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
            if (
                last_message.content in ["1", "2", "3", "4", "5"]
                and last_message.author != bot.user
            ):
                resultnum = int(last_message.content) - 1
                await last_message.add_reaction("👍")
                await smsg.delete()
                break
            # check reactions for 1-5, set resultnum
            reacts = get(bot.cached_messages, id=smsg.id).reactions
            for x in range(6):
                if reacts[x].count > 1:
                    resultnum = x
                    await smsg.delete()
                    break
            if resultnum != -1:
                break
            await asyncio.sleep(1)
        # if no input from user, set resultnum to default 0
        if resultnum == -1:
            await smsg.delete()
            resultnum = 0
        if resultnum == 5:
            await msg.edit(content="Cancelled")
            return
        yturl = info["search_result"][resultnum]["link"]
        name = info["search_result"][resultnum]["title"]

    await msg.edit(content=f"Added {name} to queue")

    # if playlist is too long, ask if user wants to add to top of queue
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT id, url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
    )
    result = mycursor.fetchall()
    addnext = False

    if len(result) > 9 and plist is False:
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
        add_to_playlist(ctx, url=yturl, arr=[])
    await ctx.message.add_reaction("👍")
    mydb.close()
    if vidplist is True:
        # TODO: make seperate function since same thing used in three places
        if "&list=" in yturl:
            plistid = yturl.split("&list=")[1][:34]
        elif "playlist?list=" in yturl:
            plistid = yturl.split("playlist?list=")[1][:34]
        plisturl = f"https://www.youtube.com/playlist?list={plistid}"
        ytplaylist = (
            str(os.popen(f"yt-dlp {plisturl} --flat-playlist --get-url").read())
            .strip()
            .split("\n")
        )
        add_to_playlist(ctx, arr=ytplaylist, url="")
    if not is_connected(ctx):
        await play_audio(ctx)


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


@bot.command(name="clear", help="Clears the queue", aliases=["c"])
async def clear(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute("SELECT url FROM playlist WHERE guild = ? ORDER BY id LIMIT 1", (ctx.guild.id,))
    firsturl = mycursor.fetchone()
    mycursor.execute("DELETE FROM playlist WHERE guild = ?", (ctx.guild.id,))
    mydb.commit()
    mydb.close()
    add_to_playlist(ctx, url=firsturl[0], arr=[])
    await ctx.message.add_reaction("👍")


@bot.command(name="skip", help="Skips current song", aliases=["next", "s"])
async def skip(ctx, num: int = 1):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    if num < 1:
        await ctx.send("Number must be greater than 0")
        return
    elif num > 1:
        mydb = sqlite3.connect(db_name)
        mycursor = mydb.cursor()
        mycursor.execute("DELETE FROM playlist WHERE guild = ? ORDER BY id LIMIT ?", (ctx.guild.id, num-1))
        mydb.commit()
        mydb.close()
    voice_client = ctx.message.guild.voice_client
    # skips by stopping current audio, play_audio will handle the rest
    voice_client.stop()
    await ctx.message.add_reaction("👍")


@bot.command(name="queue", help="Shows the current queue", aliases=["q"])
async def queue(ctx, num: int = 10):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    time1 = time.time()  # debug
    await ctx.message.add_reaction("👍")
    playlist = []
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id",
        (ctx.guild.id,),
    )
    playlist = [x[0] for x in mycursor]
    mydb.close()
    if playlist == []:
        await ctx.send("The queue is empty")
        return
    extra = ""
    if num > len(playlist):
        num = len(playlist)
    if len(playlist) > num:
        todisplay = num
        extra = f"\n {' '*10} + {len(playlist) - num} more, {len(playlist)} total"
    else:
        todisplay = len(playlist)
    msgtext = "```markdown\n"  # markdown looks nicer than plain
    yt_data = get_yt_data(playlist[:todisplay])
    for x in range(todisplay):
        title = yt_data[playlist[x]][0]
        duration_minsec = yt_data[playlist[x]][1]
        msgtext += f"{x+1}. {title} -- {duration_minsec}\n"
    print(f"Queue time taken: {time.time() - time1}")  # debug
    fullmsg = msgtext + extra
    # Discord has a 2000 character limit, so if the queue is longer than that, split it into parts
    if len(fullmsg) >= 2000:
        partmsg = "```markdown\n"
        for x in range(todisplay):
            title = yt_data[playlist[x]][0]
            duration_minsec = yt_data[playlist[x]][1]
            partmsg += f"{x+1}. {title} -- {duration_minsec}\n"
            if len(partmsg) >= 1900:
                await ctx.send(partmsg + "```")
                partmsg = "```markdown\n"
        await ctx.send(partmsg + extra + "```")
    else:
        await ctx.send(fullmsg + "```")


@bot.command(name="nowplaying", help="Shows the currently playing song", aliases=["np", "now"])
async def nowplaying(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    voice_client = ctx.message.guild.voice_client
    if not voice_client.is_playing():
        await ctx.send("Nothing is playing")
        return
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id LIMIT 1",
        (ctx.guild.id,),
    )
    url = mycursor.fetchone()[0]
    mydb.close()
    yt_data = get_yt_data([url])
    title = yt_data[url][0]
    duration_minsec = yt_data[url][1]
    await ctx.send(f"Now playing:\n```markdown\n{title} -- {duration_minsec}```")


@bot.command(
    name="shuffle", help="Shuffles the queue or provided playlist", aliases=["sh"]
)
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
    # If a playlist url is provided add to queue then shuffle
    if ytpurl is not None:
        await ctx.message.add_reaction("➕")
        await msg.edit(content="Adding playlist to queue...\n(yt-dlp query)")
        plisturl = ytpurl
        if "youtu.be" in ytpurl or "youtube.com" in ytpurl:
            # TODO: make seperate function since same thing used in three places
            if "&list=" in ytpurl:
                plistid = ytpurl.split("&list=")[1][:34]
            elif "playlist?list=" in ytpurl:
                plistid = ytpurl.split("playlist?list=")[1][:34]
            plisturl = f"https://www.youtube.com/playlist?list={plistid}"
        ytplaylist = (
            str(os.popen(f"yt-dlp {plisturl} --flat-playlist --get-url").read())
            .strip()
            .split("\n")
        )
        await msg.edit(
            content=f"Added {len(ytplaylist)} songs to queue...\n(Adding to playlist database)"
        )
        if currenturl is None:
            currenturl = ytplaylist.pop(random.randint(0, len(ytplaylist) - 1))
            ytplaylist.insert(0, currenturl)
        add_to_playlist(ctx, arr=ytplaylist, url="")
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
        mycursor.execute(
            f"UPDATE playlist SET id = {ids[i]} WHERE url = '{urls[i]}' AND guild = {ctx.guild.id}"
        )
    mydb.commit()
    mydb.close()
    await ctx.message.add_reaction("👍")
    await msg.edit(content="Shuffled...\n(Loading titles for queue)")
    await queue(ctx)
    await msg.delete()
    if not is_connected(ctx) and ytpurl is not None:
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


@bot.command(
    name="pause", help="Pauses/unpauses the bot", aliases=["resume", "unpause"]
)
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
    if not is_connected(ctx):
        await play_audio(ctx)


@bot.command(name="web", help="Shows the web interface link", aliases=["website", "w"])
async def web(ctx, msg=""):
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
        await play_audio(ctx)


bot.run(TOKEN)
