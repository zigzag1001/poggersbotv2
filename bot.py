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
bot = commands.Bot(command_prefix=["r; ", "r;", "R;", "R; "], intents=intents)

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
    "CREATE TABLE IF NOT EXISTS bot_control (guild INTEGER, action TEXT, extra TEXT, voice_channel INTEGER)"
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


def clean_url(url):
    if "\n" in url:
        url = url.split("\n")[0]
    if " " in url:
        url = url.split(" ")[0]

    
    if "youtu.be" in url or "youtube.com" in url:
        vidid = ""
        plistid = ""
        video = False

        if "watch?v=" in url:
            vidid = url.split("watch?v=")[1]
            if "&" in vidid:
                vidid = vidid.split("&")[0]
            video = True
        if "list=" in url:
            plistid = url.split("list=")[1]
            if "&" in plistid:
                plistid = plistid.split("&")[0]

        if vidid == "" and plistid == "":
            return None

        if video:
            return f"https://youtube.com/watch?v={vidid}" + (f"&list={plistid}" if plistid != "" else "")
        else:
            return f"https://youtube.com/playlist?list={plistid}"
    elif "soundcloud.com" in url:
        url = url.split("?")[0]
        return url
    else:
        return None


def isplaylist(url):
    if "youtu.be" in url or "youtube.com" in url:
        if "playlist?list=" in url:
            return True
    elif "soundcloud.com" in url:
        if "sets/" in url:
            return True
    return False


def get_arr_from_playlist(url):
    if "youtu.be" in url or "youtube.com" in url:
        # 41
        # https://music.youtube.com/playlist?list=OLAK5uy_mOrlwsA-kRRg1u2xlGlH_H94gom5ZWfzY
        # 34
        # https://www.youtube.com/playlist?list=PLK9xhCYlDnDkxBEAqQ_y0T3buIW3EZA0Z
        if "playlist?list=" in url:
            plistid = url.split("playlist?list=")[1]
            if "&" in plistid:
                plistid = plistid.split("&")[0]
            plisturl = f"https://www.youtube.com/playlist?list={plistid}"
            ytplaylist = (
                str(os.popen(f"yt-dlp {plisturl} --flat-playlist --get-url").read())
                .strip()
                .split("\n")
            )
            return ytplaylist
    elif "soundcloud.com" in url:
        url = url.split("?")[0]
        if "sets/" in url:
            scplaylist = (
                str(os.popen(f"yt-dlp {url} --flat-playlist --get-url").read())
                .strip()
                .split("\n")
            )
        return scplaylist
    return None


async def add_url(ctx, url, msg=None):
    plist = False
    vidplist = False
    name = ""

    # new clean_url isplaylist get_arr_from_playlist
    url = clean_url(url)
    if url is None:
        await ctx.send("Invalid url")
        return [None, None, None, None]

    if isplaylist(url):
        plist = True
        msgtext = "Adding playlist to queue...\n"
        await msg.edit(content=msgtext + "(yt-dlp query)")
        arr = get_arr_from_playlist(url)
        await msg.edit(
            content=f"Added {len(arr)} songs to queue...\n(Adding to playlist database)"
        )
        add_to_playlist(ctx, arr=arr, url="")
        name = f"{len(arr)} songs"
        return [plist, vidplist, url, name]
    else:
        if "&list=" in url:
            plistmsg = await ctx.send("Do you want to add the playlist to queue?")

            choices = ["✅", "❌"]
            resultnum = await choose(ctx, choices, plistmsg, 10)

            if resultnum == 0:
                vidplist = True
            else:
                url = url.split("&list=")[0]
        add_to_playlist(ctx, url=url, arr=[])
        name = get_yt_data([url])[url][0]
        return [plist, vidplist, url, name]


async def choose(ctx, choices, msg, time):
    result = -1
    channel = ctx.channel
    choices_nums = [str(x) for x in range(1, len(choices) + 1)]
    for c in choices:
        await msg.add_reaction(c)
    for _ in range(time):
        if result != -1:
            break

        # type to choose
        last_message = await channel.fetch_message(channel.last_message_id)
        if (last_message.content in choices_nums and last_message.author != bot.user):
            result = int(last_message.content) - 1
            await last_message.add_reaction("👍")
            continue

        # check reactions
        reacts = get(bot.cached_messages, id=msg.id).reactions
        for x in range(len(choices)):
            if reacts[x].count > 1:
                result = x
                break
        await asyncio.sleep(1)
    await msg.delete()
    return result


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

    moved = False
    progresstime = 0
    pureurl = ""

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
            if not moved:
                info = ytdl.extract_info(url, download=False)
                for format in info["formats"]:
                    if format["format_id"] == "251" or format["format_id"] == "http_mp3_128":
                        pureurl = format["url"]
                        break

            print(f"Url retrieve time taken: {time.time() - time1}")  # debug

            if not moved:
                audiostarttime = time.time()

            if moved:
                # continue playing audio where it left off
                moved = False
                resume_time = progresstime
                print(f"Resuming at {resume_time}")
                newffmpeg_opts = {
                    "before_options": f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {resume_time}",
                    "options": "-vn",
                }
                source = discord.FFmpegPCMAudio(pureurl, **newffmpeg_opts)
            else:
                source = discord.FFmpegPCMAudio(pureurl, **ffmpeg_opts)
            source.read()
            voice_client.play(source)
            print(f"Playing {url}")

            # main audio loop, also checks for bot control actions
            while voice_client.is_playing():
                progresstime = time.time() - audiostarttime
                mydb = sqlite3.connect(db_name)
                mycursor = mydb.cursor()
                if voice_channel != ctx.message.guild.voice_client.channel:
                    print("Bot moved")
                    moved = True
                    voice_client.stop()
                    continue
                    #voice_client.pause()
                # Checks for bot control actions
                mycursor.execute(
                    "SELECT action, extra FROM bot_control WHERE guild = ?", (ctx.guild.id,)
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
                    elif action[0] == 'ss':
                        mycursor.execute(
                            "DELETE FROM bot_control WHERE guild = ? AND action = ?",
                            (ctx.guild.id, "ss"),
                        )
                        mydb.commit()
                        mydb.close()
                        moved = True
                        skip_time = int(action[1])
                        if action[1] == None or action[1] == "":
                            skip_time = 0
                        progresstime = skip_time
                        voice_client.stop()
                        break
                await asyncio.sleep(1)
            voice_client.stop()
        except Exception as e:
            print(e)
            e = str(e)
            if len(e) > 2000:
                e = e[:1900] + "(too long)..."
            await ctx.send(f"Error playing {url}\n```\n{e}```")
        mydb = sqlite3.connect(db_name)
        mycursor = mydb.cursor()
        if not is_looping(ctx) and not moved:
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

    if message.content.lower().startswith("r;"):
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
    playnext = False
    if search.endswith("-pn!"): # janky but cant add arguments to play command
        search = search[:-4]
        playnext = True
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

    # cleans url, just in case
    urlsearch = search.strip()
    if "\n" in urlsearch:
        urlsearch = search.split("\n")[0]
    if " " in urlsearch:
        urlsearch = search.split(" ")[0]

    # If search is a url
    if re.match(final_regex, urlsearch):
        url_data = await add_url(ctx, urlsearch, msg)
        if url_data[0] is None:
            return
        plist = url_data[0]  # whether or not url is a playlist
        vidplist = url_data[1]  # whether or not url is a video with a playlist attached
        yturl = url_data[2]  # url of video
        name = url_data[3]  # name of video
    # If search is a search term
    else:
        if search in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            await msg.delete()
            await skip(ctx, int(search))
            return
        await ctx.message.add_reaction("🔎")
        search = SearchVideos(search, offset=1, mode="json", max_results=5)
        info = search.result()
        try:
            info = eval(info)
        except TypeError:
            await ctx.send("No results found / search error")
            return
        msgtext = ""
        displaynum = 5 if len(info["search_result"]) >= 5 else len(info["search_result"])
        smsg = await ctx.send(content="Searching...")
        for x in range(displaynum):
            msgtext += f'{x+1}. {info["search_result"][x]["title"]}\n'
        await smsg.edit(content=msgtext)

        choices = [f"{x+1}\N{combining enclosing keycap}" for x in range(displaynum)]
        choices.append("❌")

        resultnum = await choose(ctx, choices, smsg, 10)

        # if no input from user, set resultnum to default 0
        if resultnum == -1:
            resultnum = 0
        if resultnum == displaynum:
            await msg.edit(content="Cancelled")
            return
        yturl = info["search_result"][resultnum]["link"]
        name = info["search_result"][resultnum]["title"]
        add_to_playlist(ctx, url=yturl, arr=[])


    # if playlist is too long, ask if user wants to add to top of queue
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT id, url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
    )
    result = mycursor.fetchall()

    resultnum = 1

    if len(result) > 9 and plist is False and playnext is False:
        qmsg = await ctx.send(
            "Queue is over 10 songs, do you want to place this song at the top of the queue?"
        )

        choices = ["✅", "❌"]

        resultnum = await choose(ctx, choices, qmsg, 10)

    if (resultnum == 0 or resultnum == -1 or playnext) and plist is False:
        secondid = result[1][0]
        lastid = result[-1][0]
        mycursor.execute(
                "UPDATE playlist SET id = id + 1 WHERE id >= ? AND guild = ?",
                (secondid, ctx.guild.id),
                            )
        mydb.commit()
        mycursor.execute(
                "UPDATE playlist SET id = ? WHERE guild = ? AND id = ?",
                (secondid, ctx.guild.id, lastid + 1),
                            )
        mydb.commit()

    await msg.edit(content=f"Added [{name}](<{yturl}>) to queue")

    await ctx.message.add_reaction("👍")
    mydb.close()
    if vidplist is True:
        if "&list=" in yturl:
            plistid = yturl.split("&list=")[1]
            if "&" in plistid:
                plistid = plistid.split("&")[0]
        else:
            return

        plisturl = f"https://www.youtube.com/playlist?list={plistid}"
        ytplaylist = get_arr_from_playlist(plisturl)

        currentid = yturl.split("?v=")[1]
        if "&" in currentid:
            currentid = currentid.split("&")[0]
        currenturl = f"https://www.youtube.com/watch?v={currentid}"
        ytplaylist.remove(currenturl)

        add_to_playlist(ctx, arr=ytplaylist, url="")

        await ctx.send(f"Added {len(ytplaylist)} songs to queue...")
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
        await ctx.send(f"Skipped to song +{num}")
    voice_client = ctx.message.guild.voice_client
    # skips by stopping current audio, play_audio will handle the rest
    voice_client.stop()
    await ctx.message.add_reaction("👍")


@bot.command(name="queue", help="Shows the current queue", aliases=["q"])
async def queue(ctx, num = 10):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    try:
        num = int(num)
    except ValueError:
        await ctx.send("Invalid number, usage: `r;queue [number of songs to show]`")
        return
    time1 = time.time()  # debug
    await ctx.message.add_reaction("👍")
    playlist = []
    ids = []
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url, id FROM playlist WHERE guild = ? ORDER BY id",
        (ctx.guild.id,),
    )
    for x in mycursor:
        playlist.append(x[0])
        ids.append(x[1])
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
    title = yt_data[playlist[0]][0]
    duration_minsec = yt_data[playlist[0]][1]
    msgtext += f"> {ids[0]}. {title} -- {duration_minsec}\n"
    for x in range(1, todisplay):
        title = yt_data[playlist[x]][0]
        duration_minsec = yt_data[playlist[x]][1]
        msgtext += f"       {x+1}. {title} -- {duration_minsec}\n"
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
    await queue(ctx, 2)


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

        ytpurl = clean_url(ytpurl)

        if ytpurl is None:
            await ctx.send("Invalid url")
            return
        elif isplaylist(ytpurl) is False:
            await ctx.send("Not a playlist url")
            return

        ytplaylist = get_arr_from_playlist(ytpurl)

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
        f"SELECT url, id FROM playlist WHERE guild = {ctx.guild.id} ORDER BY id"
    )
    result = mycursor.fetchall()

    urls_list = [x[0] for x in result]

    currentid = result[0][1]

    del urls_list[0]

    random.shuffle(urls_list)

    mycursor.execute(
        "DELETE FROM playlist WHERE guild = ? AND id > ?", (ctx.guild.id, currentid)
    )

    mydb.commit()
    mydb.close()

    add_to_playlist(ctx, arr=urls_list, url="")

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


@bot.command(name="ss", help="Skips to a certain time in the song", aliases=["skipsec", "skipseconds"])
async def ss(ctx, time=None):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    if not is_playing(ctx):
        await ctx.send("Nothing is playing")
        return
    if time is None:
        await ctx.send("Please provide a time to skip to")
        return

    if re.match(r"^\d+:\d+$", time):
        time = time.split(":")
        time = int(time[0]) * 60 + int(time[1])
    elif re.match(r"^\d+:\d+:\d+$", time):
        time = time.split(":")
        time = int(time[0]) * 3600 + int(time[1]) * 60 + int(time[2])
    elif re.match(r"^\d+$", time):
        time = int(time)
    elif re.match(r"^\d+h\d+m\d+s$", time):
        time = time.split("h")
        h = int(time[0])
        time = time[1].split("m")
        m = int(time[0])
        time = time[1].split("s")
        s = int(time[0])
        time = h * 3600 + m * 60 + s
    elif re.match(r"^\d+m\d+s$", time):
        time = time.split("m")
        m = int(time[0])
        time = time[1].split("s")
        s = int(time[0])
        time = m * 60 + s
    elif re.match(r"^\d+s$", time):
        time = int(time[:-1])
    elif re.match(r"^\d+m$", time):
        time = int(time[:-1]) * 60
    else:
        await ctx.send("Invalid time format")
        return

    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "INSERT INTO bot_control (guild, action, extra) VALUES (?, ?, ?)",
        (ctx.guild.id, "ss", time),
    )
    mydb.commit()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id LIMIT 1", (ctx.guild.id,)
    )
    currenturl = mycursor.fetchone()
    mycursor.execute(
        "SELECT duration FROM yt_data WHERE url = ?", (currenturl[0],)
    )
    duration = mycursor.fetchone()[0]
    mydb.close()
    h = time // 3600
    m = time % 3600 // 60
    s = time % 3600 % 60
    if h == 0:
        time = f"{m}:{s:02d}"
    else:
        time = f"{h}:{m}:{s:02d}"
    await ctx.send(f"{time} / {duration}")
    await ctx.message.add_reaction("👍")


@bot.command(name="pn", help="Just like play, but places song next", aliases=["playnext", "pnext"])
async def pn(ctx, *, search: str = None):
    search = search + "-pn!"  # janky but cant add arguments to play command
    await play(ctx, search=search)

bot.run(TOKEN)
