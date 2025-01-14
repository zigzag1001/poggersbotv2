import os
import re
import html
import time
import copy
import urllib
import yt_dlp
import asyncio
import random
import sqlite3
import datetime
from dotenv import load_dotenv
from youtubesearchpython import SearchVideos

import discord
from discord.ext import commands
from discord.utils import get

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX")
prefix_variations = [
    PREFIX.lower(),
    PREFIX.lower() + " ",
    PREFIX.upper(),
    PREFIX.upper() + " ",
]
PROXY_URL = os.getenv("PROXY")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=prefix_variations, intents=intents)

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
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -headers 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0'",
    "options": "-vn",
}

if PROXY_URL:
    ytdlp_format_options["proxy"] = PROXY_URL

    ffmpeg_opts["before_options"] += f" -http_proxy {PROXY_URL}"

    proxy_handler = urllib.request.ProxyHandler(
        {'http':PROXY_URL, 'https':PROXY_URL}
    )
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)


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
def colorize(string, color):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "purple": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "black": "\033[30m",
    }
    reset = "\033[0m"
    return colors[color] + string + reset


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
    action = mycursor.fetchall()
    action = [x[0] for x in action]
    mydb.close()
    if action == []:
        return False
    elif "loop" in action:
        print("looping is true")
        return True
    else:
        return False


def is_looping_queue(ctx):
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute("SELECT action FROM bot_control WHERE guild = ?", (ctx.guild.id,))
    action = mycursor.fetchall()
    action = [x[0] for x in action]
    mydb.close()
    if action == []:
        return False
    elif "loopqueue" in action:
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
            # only needed since some data is cached but incorrect
            if (
                any(x in resultsdict[url][0] for x in ["&quot;", "&#39;", "&amp;"])
                or resultsdict[url][0] == ""
            ):
                if resultsdict[url][0] == "":
                    resultsdict[url] = ("Unknown", resultsdict[url][1])
                resultsdict[url] = (
                    resultsdict[url][0]
                    .replace("&quot;", '"')
                    .replace("&#39;", "'")
                    .replace("&amp;", "&"),
                    resultsdict[url][1],
                )
                mycursor.execute(
                    "UPDATE yt_data SET name = ?, duration = ? WHERE url = ?",
                    (resultsdict[url][0], resultsdict[url][1], url),
                )
            urls_list_data[url] = resultsdict[url]
            print(f"get_yt_data Found in cache: {resultsdict[url]}")
        elif url.startswith("search://"):
            name = url.split("search://")[1]
            duration = "0:00"
            try:
                mycursor.execute(
                    "INSERT INTO yt_data (url, name, duration) VALUES (?, ?, ?)",
                    (url, name, duration),
                )
                mydb.commit()
            except sqlite3.IntegrityError:
                print("get_yt_data IntegrityError")
            urls_list_data[url] = (name, duration)
        else:
            # html extraction
            html_res = None
            try:
                response = urllib.request.urlopen(url)
                html_res = response.read().decode()
            except urllib.error.HTTPError:
                print(colorize("HTTPError", "red"), url)
                html_res = None
            except Exception as e:
                print(colorize("Error", "red"), url)
                print(e)
                html_res = None
            if "youtu.be" in url or "youtube.com" in url:
                name = (
                    re.search(r"<title>(.*?)</title>", html_res)
                    .group(1)
                    .split(" - YouTube")[0]
                )
                if name is None or name == "":
                    print(colorize("YTError", "red"), html_res)
                try:
                    duration = re.search(r'"lengthSeconds":"(.*?)"', html_res).group(1)
                except AttributeError:
                    duration = None
            elif "soundcloud.com" in url:
                time1 = time.time()  # debug
                if "api-v2" in url:
                    data = (
                        os.popen(f"yt-dlp {url} --get-title --get-duration")
                        .read()
                        .strip()
                        .split("\n")
                    )
                    name = data[0]
                    duration = data[1]
                    min = int(duration.split(":")[0])
                    sec = int(duration.split(":")[1])
                    duration = str(min * 60 + sec)
                else:
                    name = re.search(
                        r'<meta property="og:title" content="(.*?)">', html_res
                    ).group(1)
                    try:
                        duration = re.search(
                            r'<span aria-hidden="true">(\d+):(\d+)</span>', html_res
                        )
                        mins = int(duration.group(1))
                        secs = int(duration.group(2))
                        duration = str(mins * 60 + secs)
                    except AttributeError:
                        duration = None
                print(
                    f"Soundcloud name duration time taken: {time.time() - time1}"
                )  # debug
            elif html_res is not None and "<title>" in html_res:
                name = get_html_title(url, html_res)
                duration = None
            elif any(
                url.split("?")[0].endswith(x)
                for x in [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".webm"]
            ):
                name = url.split("/")[-1].split("?")[0]
                duration = None
            else:
                print("Not a valid url")
                name = "Invalid url"
                duration = None

            if name is None or name == "":
                name = "Unknown"
            else:
                name = (
                    name.replace("&quot;", '"')
                    .replace("&#39;", "'")
                    .replace("&amp;", "&")
                )

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
                print("get_yt_data IntegrityError")
            urls_list_data[url] = (name, duration_minsec)
    mydb.close()
    return urls_list_data


# Takes url, removes extra arguments, validates
# returns cleaned url or None if invalid
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
        elif "youtu.be" in url:
            vidid = url.split("youtu.be/")[1]
            if "?" in vidid:
                vidid = vidid.split("?")[0]
            video = True
        elif "/shorts/" in url:
            vidid = url.split("/shorts/")[1]
            if "?" in vidid:
                vidid = vidid.split("?")[0]
            video = True

        if "list=" in url:
            plistid = url.split("list=")[1]
            if "&" in plistid:
                plistid = plistid.split("&")[0]

        if vidid == "" and plistid == "":
            return None

        if video:
            return f"https://youtube.com/watch?v={vidid}" + (
                f"&list={plistid}" if plistid != "" else ""
            )
        else:
            return f"https://youtube.com/playlist?list={plistid}"
    elif "soundcloud.com" in url:
        url = url.split("?")[0]
        return url
    elif "spotify.com" in url:
        if "?" in url:
            url = url.split("?")[0]
        if "/track/" in url:
            return url
        elif "/playlist/" in url:
            return url
        elif "/album/" in url:
            return url
        else:
            return None
    else:
        return url


# Takes url, returns True if it's a playlist
def isplaylist(url):
    if "youtu.be" in url or "youtube.com" in url:
        if "playlist?list=" in url:
            return True
    elif "soundcloud.com" in url:
        if "sets/" in url:
            return True
    elif "spotify.com" in url:
        if "/playlist/" in url or "/album/" in url:
            return True
    return False


# Takes url, returns array of urls if it's a playlist
# returns None if not a playlist
def get_arr_from_playlist(url):
    if "youtu.be" in url or "youtube.com" in url:
        # 41
        # https://music.youtube.com/playlist?list=OLAK5uy_mOrlwsA-kRRg1u2xlGlH_H94gom5ZWfzY
        # 34
        # https://www.youtube.com/playlist?list=PLK9xhCYlDnDkxBEAqQ_y0T3buIW3EZA0Z
        if "list=" in url:
            plistid = url.split("list=")[1]
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
    elif "spotify.com" in url:
        # get names of songs and format playlist to search://songname
        if "/playlist/" in url or "/album/" in url:
            response = urllib.request.urlopen(url)
            html_res = response.read().decode()
            songs = re.findall(r"https://open.spotify.com/track/\w+", html_res)
            spotifyplaylist = []
            for song in songs:
                spotifyplaylist.append(song)
            return spotifyplaylist
    return None


# takes normal url, returns direct file url
# None if not supported
def get_direct_url(url):
    if "youtu.be" in url or "youtube.com" in url:
        info = ytdl.extract_info(url, download=False)
        for format in info["formats"]:
            if format["format_id"] == "251":
                return format["url"]
        if "233" in [x["format_id"] for x in info["formats"]]:
            for format in info["formats"]:
                if format["format_id"] == "233":
                    return format["url"]
    elif "soundcloud.com" in url:
        info = ytdl.extract_info(url, download=False)
        for format in info["formats"]:
            if format["format_id"] == "http_mp3_128":
                return format["url"]
    elif url.startswith("search://"):
        search = url.split("search://")[1]
        search = "".join(e for e in search if e.isalnum() or e.isspace())
        search = SearchVideos(search + " lyric", offset=1, mode="json", max_results=1)
        results = search.result()
        evald_results = eval(results)
        ytlink = evald_results["search_result"][0]["link"]
        yttitle = evald_results["search_result"][0]["title"]
        yttitle = "".join(e for e in yttitle if e.isalnum() or e.isspace())
        print(colorize(yttitle, "green"), ytlink)
        info = ytdl.extract_info(ytlink, download=False)
        for format in info["formats"]:
            if format["format_id"] == "251":
                return format["url"]
    elif any(
        url.split("?")[0].endswith(x)
        for x in [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".webm"]
    ):
        return url
    else:
        return get_direct_url("search://" + get_html_title(url))
    return None


# spotify needs to be searched on youtube
def needs_search(url):
    if "youtu.be" in url or "youtube.com" in url:
        return False
    elif "soundcloud.com" in url:
        return False
    elif any(
        url.split("?")[0].endswith(x)
        for x in [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".webm"]
    ):
        return False
    else:
        print("Needs search")
        return True


# get title from html
def get_html_title(url, html_res=None):
    if html_res is None:
        response = urllib.request.urlopen(url)
        html_res = response.read().decode()
    if "spotify.com" in url:
        song = html.unescape(re.findall(r"<title>(.+?) -", html_res)[0])
        artist = html.unescape(
            re.findall(r"(?<=by\s)(.*?)(?=\s\|\sSpotify)", html_res)[0]
        )
        title = song + " - " + artist.strip(",")
        return title
    elif "deezer.com" in url:
        song = re.findall(
            r"<title>(.+?): listen with lyrics | Deezer</title>", html_res
        )
        return song[0]
    else:
        return re.search(r"<title>(.+?)</title>", html_res).group(1)


# Takes context, url, and optional message to edit
# adds url to playlist database
# If url is a playlist, adds all songs to playlist database
# returns [is playlist, is video and playlist, url, name]
async def add_url(ctx, url, msg=None):
    plist = False
    vidplist = False
    name = ""
    if msg is None:
        msg = await ctx.send("Adding to queue...")

    # new clean_url isplaylist get_arr_from_playlist
    url = clean_url(url)
    # TEMP
    if "spotify.com" in url:
        await ctx.send("Spotify support is super buggy!!!")
    if url is None:
        await ctx.send("Invalid url")
        return [None, None, None, None]

    if isplaylist(url):
        if "spotify.com" in url:
            await ctx.send("Spotify playlists only get the first 30 songs!!!")
        plist = True
        msgtext = "Adding playlist to queue...\n"
        await msg.edit(content=msgtext + "(yt-dlp query)")
        arr = get_arr_from_playlist(url)
        if arr is None:
            await ctx.send("Error getting playlist")
            return [None, None, None, None]
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


# Takes context, string array of choices, message to edit, and time to choose
# max 10 choices
# can choose by typing or reacting
# plain number, prefix + number, prefix + play + number
# delete message after choosing
# returns index of choice
async def choose(ctx, choices, msg, time):
    result = -1
    channel = ctx.channel
    if len(choices) >= 10:
        await ctx.send("Internal error: Too many choices")
        return -1
    choices_nums = [str(x) for x in range(1, len(choices) + 1)]
    temp = choices_nums.copy()
    for c in temp:
        choices_nums.append(PREFIX.lower() + c)
        choices_nums.append(PREFIX.lower() + "p " + c)
        choices_nums.append(PREFIX.lower() + "play " + c)
    for c in choices:
        await msg.add_reaction(c)
    for _ in range(time):
        if result != -1:
            break

        # type to choose
        last_message = await channel.fetch_message(channel.last_message_id)
        clean_msg = last_message.content.lower().strip()
        if clean_msg in choices_nums and last_message.author != bot.user:
            result = int(clean_msg.strip(PREFIX.lower() + "play")) - 1
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
    if ctx.author.voice.channel.permissions_for(ctx.guild.me).connect is False:
        print(
            colorize(ctx.guild.name, "red"),
            f"- No permission to connect to {ctx.author.voice.channel.name}",
        )
        await ctx.send(
            f'ERROR - "{ctx.author.voice.channel.name}" - is either private or bot dosent have permissions for it'
        )
        return
    five_times = 0  # For checking if bot is inactive
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
        print(
            f"{colorize(ctx.guild.name, 'green')} - Connected to {ctx.author.voice.channel.name}"
        )

    moved = False
    filter = {}
    progresstime = 0
    pureurl = ""
    errors = 0

    while is_connected(ctx):
        if is_playing(ctx):
            print(
                f"{colorize(ctx.guild.name, 'red')} - Already playing, returning (in loop)"
            )  # debug
            return

        # Checks if bot is inactive and if songs have been added in web
        if playlist == [] and is_connected(ctx):
            five_times += 5
            if five_times == (60 * 30):
                await ctx.send("Inactive for 30 minutes, disconnecting...")
                print(
                    f"{colorize(ctx.guild.name, 'red')} - Inactive for 30 minutes, disconnecting"
                )
                await stop(None, ctx.guild)
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
                pureurl = get_direct_url(url)
                if pureurl is None:
                    await ctx.send(f"Error getting {url}")
                    print(f"{colorize(ctx.guild.name, 'red')} - Error getting {url}")

                    mydb = sqlite3.connect(db_name)
                    mycursor = mydb.cursor()
                    mycursor.execute(
                        "DELETE FROM playlist WHERE url = ? AND guild = ? ORDER BY id LIMIT 1",
                        (url, ctx.guild.id),
                    )
                    mydb.commit()
                    mydb.close()

                    errors += 1
                    if errors >= 10:
                        await ctx.send("Too many errors, stopping")
                        await stop(None, ctx.guild)
                    continue

            print(f"Url retrieve time taken: {time.time() - time1}")  # debug

            ffmpeg_opts_copy = copy.deepcopy(ffmpeg_opts)

            # filter
            if ctx.guild.id not in filter.keys():
                filter[ctx.guild.id] = []
            if filter[ctx.guild.id] != []:
                print(f"{filter[ctx.guild.id]=}")
                s = " -af "
                for f in filter[ctx.guild.id]:
                    s += f + ","
                ffmpeg_opts_copy["options"] += s[:-1]

            if not moved:
                audiostarttime = time.time()

            print(f"{colorize(ctx.guild.name, 'green')} - Playing {url}")
            if moved:
                # continue playing audio where it left off
                moved = False
                resume_time = progresstime
                print(f"Resuming at {resume_time}")
                ffmpeg_opts_copy["before_options"] += f" -ss {resume_time}"
                if PROXY_URL:
                    ffmpeg_opts_copy["before_options"] += f" -http_proxy {PROXY_URL}"
                source = discord.FFmpegPCMAudio(pureurl, **ffmpeg_opts_copy)
            else:
                source = discord.FFmpegPCMAudio(pureurl, **ffmpeg_opts_copy)
            source.read()
            voice_client.play(source)

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
                # Checks for bot control actions
                mycursor.execute(
                    "SELECT action, extra FROM bot_control WHERE guild = ?",
                    (ctx.guild.id,),
                )
                action = mycursor.fetchall()
                actions = dict(action)
                mydb.close()
                if actions != {}:
                    mydb = sqlite3.connect(db_name)
                    mycursor = mydb.cursor()
                    # skpis by stopping current audio, loop goes on to next song
                    if "skip" in actions.keys():
                        print(f"{colorize(ctx.guild.name, 'green')} - Skipping")
                        voice_client.stop()
                        mycursor.execute(
                            "DELETE FROM bot_control WHERE guild = ? AND action = ?",
                            (ctx.guild.id, "skip"),
                        )
                        mydb.commit()
                        mydb.close()
                    elif "ss" in actions.keys():
                        mycursor.execute(
                            "DELETE FROM bot_control WHERE guild = ? AND action = ?",
                            (ctx.guild.id, "ss"),
                        )
                        mydb.commit()
                        mydb.close()
                        moved = True
                        skip_time = int(actions["ss"])
                        if actions["ss"] == None or actions["ss"] == "":
                            skip_time = 0
                        progresstime = skip_time
                        voice_client.stop()
                        break
                    elif "fffilter" in actions.keys():
                        mycursor.execute(
                                "DELETE FROM bot_control WHERE guild = ? AND action = ?",
                                (ctx.guild.id, "fffilter"),
                                                        )
                        mydb.commit()
                        mydb.close()
                        tmp = actions["fffilter"]
                        if tmp in ["list", "ls"]:
                            await ctx.send(f"Current filter: {filter[ctx.guild.id]}")
                            continue
                        if tmp.startswith("add"):
                            tmp = tmp.split("add ")[1]
                            filter[ctx.guild.id].append(tmp)
                        elif tmp.startswith("remove"):
                            tmp = tmp.split("remove ")[1]
                            if tmp in filter[ctx.guild.id]:
                                await ctx.send(f"Removed {tmp} from filter")
                                filter[ctx.guild.id].remove(tmp)
                            else:
                                for fi, f in enumerate(filter[ctx.guild.id]):
                                    if tmp in f:
                                        await ctx.send(f"Removed {tmp} from filter")
                                        filter[ctx.guild.id][fi] = filter[ctx.guild.id][fi].replace(tmp, "").strip(",")
                        elif tmp in ["none", "", "stop"]:
                            filter[ctx.guild.id] = []
                        else:
                            filter[ctx.guild.id] = [actions["fffilter"]]
                        moved = True
                        skip_time = progresstime
                        voice_client.stop()
                        break
                await asyncio.sleep(1)
            voice_client.stop()
            errors = 0
        except Exception as e:
            errors += 1
            print(
                colorize(ctx.guild.name, "red"),
                "\n",
                url,
                "\n",
                "\n=======\n",
                e,
                "\n=======\n",
            )
            e = str(e)
            if e.startswith("ERROR: [youtube]"):
                e = e.split("ERROR: [youtube]")[1]
            else:
                e = "Unknown error"
            if len(e) > 2000:
                e = e[:1900] + "(too long)..."
            await ctx.send(f"Error playing {url}\n```\n{e}```")
            if errors >= 10:
                await ctx.send("Too many errors, stopping")
                await stop(None, ctx.guild)
        mydb = sqlite3.connect(db_name)
        mycursor = mydb.cursor()
        if not is_looping(ctx) and not moved:
            mycursor.execute(
                "DELETE FROM playlist WHERE url = ? AND guild = ? ORDER BY id LIMIT 1",
                (url, ctx.guild.id),
            )
            mydb.commit()
            if is_looping_queue(ctx):
                add_to_playlist(ctx, url=url, arr=[])

        mycursor.execute(
            "SELECT url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
        )
        playlist = [x[0] for x in mycursor]
        mydb.close()


# Events
@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    print("Connected to the following guilds:")
    for guild in bot.guilds:
        print(f"{colorize(guild.name, 'green')} (id: {guild.id})")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help"))


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower().startswith(PREFIX.lower()):
        print(
            f"{colorize(message.guild.name, 'green')} - {colorize(message.author.name, 'cyan')} - {message.content}"
        )
        await bot.process_commands(message)


# Properly handles empty voice channel and forced disconnects
@bot.event
async def on_voice_state_update(member, before, after):
    bot_voice_channel = member.guild.voice_client
    if bot_voice_channel is None or bot_voice_channel.channel.members == []:
        return
    # stop if bot is alone in voice channel
    if bot_voice_channel.channel.members == [bot.user]:
        print(f"{colorize(member.guild.name, 'red')} - Bot alone, leaving...")
        await stop(None, member.guild)
        return
    # stop if bot is force disconnected from voice channel
    if member == bot.user and member not in bot_voice_channel.channel.members:
        print(
            f"{colorize(member.guild.name, 'red')} - Bot force disconnected, leaving..."
        )
        await asyncio.sleep(5)
        if member not in bot_voice_channel.channel.members:
            await stop(None, member.guild)
        else:
            print(
                f"{colorize(member.guild.name, 'green')} - Nevermind! Bot rejoined, continuing..."
            )
        return


# Commands


# handles search and url adding to queue
# start play_audio if not already playing
@bot.command(
    name="play",
    help="Adds a song to queue, can be url or search term",
    aliases=["p", "search", "add", "Play", "P", "Search", "Add"],
)
async def play(ctx, *, search: str = None):
    ytplaylist = []
    playnext = False
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if ctx.message.attachments:
        url = ctx.message.attachments[0].url
        print(url)
        search = url
    if search is None:
        await skip(ctx)
        if not is_playing(ctx):
            await play_audio(ctx)
        return
    if search.endswith("-pn!"):  # janky but cant add arguments to play command
        search = search[:-4]
        playnext = True

    # Check if search is a url using regex
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    vidplist = False
    plist = False

    # cleans url, just in case
    urlsearch = search.strip()
    if "\n" in urlsearch:
        urlsearch = search.split("\n")[0]
    if " " in urlsearch:
        urlsearch = search.split(" ")[0]

    # If search is a url
    if re.match(regex, urlsearch):
        msg = await ctx.send("Adding to queue...")
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
            return
        msg = await ctx.send("Adding to queue...")
        await ctx.message.add_reaction("🔎")
        search = SearchVideos(search, offset=1, mode="json", max_results=5)
        info = search.result()
        try:
            info = eval(info)
        except TypeError:
            await ctx.send("No results found / search error")
            return
        msgtext = ""
        displaynum = (
            5 if len(info["search_result"]) >= 5 else len(info["search_result"])
        )
        smsg = await ctx.send(content="Searching...")
        for x in range(displaynum):
            msgtext += f'{x+1}. {info["search_result"][x]["title"]}\n'
        await smsg.edit(content=msgtext)

        choices = [f"{x+1}\N{COMBINING ENCLOSING KEYCAP}" for x in range(displaynum)]
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
    if len(result) <= 1:
        playnext = False

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

    temp_yturl = yturl
    if yturl.startswith("search://"):
        yturl = "".join(e for e in yturl if e.isalnum() or e.isspace())
        temp_yturl = f"https://www.youtube.com/results?search_query={yturl.split('search://')[1].replace(' ', '+')}"

    await msg.edit(content=f"Added [{name}](<{temp_yturl}>) to queue")

    await ctx.message.add_reaction("👍")
    mydb.close()
    if vidplist is True:
        if "&list=" in yturl:
            plistid = yturl.split("&list=")[1]
            if "&" in plistid:
                plistid = plistid.split("&")[0]
        else:
            print("No list id found")
            return

        plisturl = f"https://www.youtube.com/playlist?list={plistid}"
        ytplaylist = get_arr_from_playlist(plisturl)

        if ytplaylist is None or ytplaylist == [] or ytplaylist == [""]:
            await ctx.send("Nevermind, Error getting playlist")
        else:
            currentid = yturl.split("?v=")[1]
            if "&" in currentid:
                currentid = currentid.split("&")[0]
            currenturl = f"https://www.youtube.com/watch?v={currentid}"
            if currenturl in ytplaylist:
                ytplaylist.remove(currenturl)

            add_to_playlist(ctx, arr=ytplaylist, url="")

            await ctx.send(f"Added {len(ytplaylist)} songs to queue...")
    if not is_connected(ctx):
        try:
            await play_audio(ctx)
        except Exception as e:
            print(f"{colorize(ctx.guild.name, 'red')} - Error playing audio: {e}")
            await ctx.send("Error playing audio")
            await stop(None, ctx.guild)


@bot.command(
    name="stop",
    help="Stops playing audio, clear queue and disconnects bot",
    aliases=["disconnect", "dc", "leave"],
)
async def stop(ctx, guild=None):
    if ctx is not None:
        if not is_user_connected(ctx):
            await ctx.send("You are not connected to a voice channel")
            return
        if not is_connected(ctx):
            await ctx.send("I am not connected to a voice channel")
            return
        guild = ctx.guild
    print(f"{colorize(guild.name, 'red')} - Stopping and disconnecting...")
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute("DELETE FROM playlist WHERE guild = ?", (guild.id,))
    mycursor.execute("DELETE FROM bot_control WHERE guild = ?", (guild.id,))
    mydb.commit()
    mydb.close()
    voice_client = guild.voice_client
    if voice_client is not None:
        await voice_client.disconnect()


@bot.command(name="clear", help="Clears the queue", aliases=["c", "cl", "C", "Cl"])
async def clear(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id LIMIT 1", (ctx.guild.id,)
    )
    firsturl = mycursor.fetchone()
    mycursor.execute("DELETE FROM playlist WHERE guild = ?", (ctx.guild.id,))
    mydb.commit()
    mydb.close()
    add_to_playlist(ctx, url=firsturl[0], arr=[])
    await ctx.message.add_reaction("👍")


@bot.command(name="skip", help="Skips current song", aliases=["next", "s", "S"])
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
        mycursor.execute(
            "DELETE FROM playlist WHERE guild = ? ORDER BY id LIMIT ?",
            (ctx.guild.id, num - 1),
        )
        mydb.commit()
        mydb.close()
        await ctx.send(f"Skipped to song +{num}")
    if is_looping(ctx):
        mydb = sqlite3.connect(db_name)
        mycursor = mydb.cursor()
        mycursor.execute(
            "DELETE FROM playlist WHERE guild = ? ORDER BY id LIMIT 1", (ctx.guild.id,)
        )
        mydb.commit()
        mydb.close()
    voice_client = ctx.message.guild.voice_client
    # skips by stopping current audio, play_audio will handle the rest
    voice_client.stop()
    await ctx.message.add_reaction("👍")


@bot.command(name="queue", help="Shows the current queue", aliases=["q", "list", "Q"])
async def queue(ctx, num: str = "10"):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if num.isdigit():
        num = int(num)
    else:
        await ctx.send(
            f"Invalid number, usage: `{PREFIX}queue [number of songs to show]`"
        )
        return
    time1 = time.time()  # debug
    await ctx.message.add_reaction("👍")
    queuemsg = await ctx.send("Loading queue...")
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

    try:
        yt_data = get_yt_data(playlist[:todisplay])
    except Exception as e:
        print(f"{colorize(ctx.guild.name, 'red')} - Error getting yt data: {e}")
        await queuemsg.edit(content="Error getting yt data")
        return
    await queuemsg.delete()

    # embed
    embed = discord.Embed(color=discord.Color.green())

    title = yt_data[playlist[0]][0]
    duration_minsec = yt_data[playlist[0]][1]
    url = playlist[0]
    if url.startswith("search://"):
        url = f"https://www.youtube.com/results?search_query={url.split('search://')[1].replace(' ', '+')}+lyric"
    elif url.startswith("https://open.spotify.com/track/"):
        url = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+lyric"
    embed.add_field(
        value=f"> {ids[0]}. **[{title}]({url})** -- {duration_minsec}",
        inline=False,
        name="",
    )

    for x in range(1, todisplay):
        title = yt_data[playlist[x]][0]
        duration_minsec = yt_data[playlist[x]][1]
        url = playlist[x]
        if url.startswith("search://"):
            url = f"https://www.youtube.com/results?search_query={url.split('search://')[1].replace(' ', '+')}+lyric"
        elif url.startswith("https://open.spotify.com/track/"):
            url = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+lyric"
        embed.add_field(
            value=f"\\> {x+1}. [{title}]({url}) -- {duration_minsec}",
            inline=False,
            name="",
        )
        if len(embed.fields) == 25:
            await ctx.send(embed=embed)
            embed = discord.Embed(color=discord.Color.green())
    embed.set_footer(text=extra)

    await ctx.send(embed=embed)
    print(
        f"{colorize(ctx.guild.name, 'green')} - Queue time taken: {time.time() - time1}"
    )  # debug
    return


@bot.command(
    name="nowplaying",
    help="Shows the currently playing song",
    aliases=["np", "now", "Np"],
)
async def nowplaying(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    await queue(ctx, "2")


@bot.command(
    name="shuffle", help="Shuffles the queue or provided playlist", aliases=["sh", "Sh"]
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
        elif isplaylist(ytpurl) is False and "list=" not in ytpurl:
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
    await msg.edit(content="Shuffled...")
    asyncio.create_task(queue(ctx))
    await msg.delete()
    if not is_connected(ctx) and ytpurl is not None:
        await play_audio(ctx)


@bot.command(name="loop", help="Loops the current song", aliases=["l", "L", "Loop"])
async def loop(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    if ctx.message.content.lower().endswith(
        "all"
    ) or ctx.message.content.lower().endswith("queue"):
        await loopall(ctx)
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
    name="web", help="Shows the web interface link", aliases=["website", "w", "W"]
)
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
        print(f"{colorize(ctx.guild.name, 'green')} - Joining voice channel...")
        await ctx.author.voice.channel.connect()
        await play_audio(ctx)


@bot.command(
    name="ss",
    help="Skips to a certain time in the song",
    aliases=["skipsec", "skipseconds"],
)
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
    duration = get_yt_data([currenturl[0]])[currenturl[0]][1]
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


@bot.command(
    name="pn",
    help="Just like play, but places song next",
    aliases=["playnext", "pnext", "Pn"],
)
async def pn(ctx, *, search: str = None):
    search = search + "-pn!"  # janky but cant add arguments to play command
    await play(ctx, search=search)


@bot.command(
    name="loopall",
    help="Loops the entire queue",
    aliases=["la", "loopqueue"],
)
async def loopall(ctx):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if not is_connected(ctx):
        await ctx.send("I am not connected to a voice channel")
        return
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    if is_looping_queue(ctx):
        mycursor.execute(
            "DELETE FROM bot_control WHERE guild = ? AND action = ?",
            (ctx.guild.id, "loopqueue"),
        )
        await ctx.send("Stopped looping queue")
    else:
        mycursor.execute(
            "INSERT INTO bot_control (guild, action) VALUES (?, ?)",
            (ctx.guild.id, "loopqueue"),
        )
        await ctx.send("Looping queue")
    await ctx.message.add_reaction("👍")
    mydb.commit()
    mydb.close()


@bot.command(
    name="delete",
    help="Deletes a song from the queue",
    aliases=["del"],
)
async def delete(ctx, num: str = "1"):
    if not is_user_connected(ctx):
        await ctx.send("You are not connected to a voice channel")
        return
    if num.lower() == "all":
        await clear(ctx)
        return
    if num.isdigit():
        num = int(num)
    else:
        await ctx.send("Invalid number")
        return

    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT url FROM playlist WHERE guild = ? ORDER BY id", (ctx.guild.id,)
    )
    urls = mycursor.fetchall()
    if urls == []:
        await ctx.send("The queue is empty")
        return
    elif num > len(urls):
        await ctx.send("Number is greater than the queue length")
        return
    else:
        url = urls[num - 1][0]
        mycursor.execute(
            "DELETE FROM playlist WHERE guild = ? AND url = ? ORDER BY id LIMIT 1",
            (ctx.guild.id, url),
        )
        mydb.commit()
        await ctx.send(f"Deleted [{get_yt_data([url])[url][0]}](<{url}>) from queue")


@bot.command(
    name="cls",
    help="Clears the bots messages from the last 5 hours",
)
async def cls(ctx, hours: str = "1", limit: str = "100"):
    if not hours.isdigit():
        await ctx.send("Invalid hours number")
        return
    if not limit.isdigit():
        await ctx.send("Invalid message limit number")
        return
    if int(limit) < 100:
        await ctx.send("Limit must be greater than 100")
        return
    hours = int(hours)
    limit = int(limit)

    def is_bot(m):
        return m.author == bot.user

    await ctx.message.add_reaction("👍")

    time1 = time.time()

    deleted = await ctx.channel.purge(
        limit=limit,
        after=datetime.datetime.now() - datetime.timedelta(hours=hours),
        check=is_bot,
    )
    await ctx.send(f"Deleted {len(deleted)} messages in {time.time() - time1} seconds")


@bot.command(
    name="fffilter",
    help="ffmpeg filter for audio",
)
async def fffilter(ctx, *, filter: str = None):
    if filter is None:
        await ctx.send("Please provide a filter")
        return

    filter = filter.strip(",")

    # validate filter
    # and only allow possible ffmpeg filters
    regex = r"^(?:\w+?=[^,]+,)*?\w+=[^,\n]+$|^\w+$"
    test = filter
    if "add" in filter or "remove" in filter:
        test = filter.replace("add ", "").replace("remove ", "")
    if not re.match(regex, test):
        await ctx.send(f"Invalid filter '{filter}'")
        return

    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT extra FROM bot_control WHERE guild = ? AND action = ?",
        (ctx.guild.id, "fffilter"),
    )
    result = mycursor.fetchone()
    if result is not None:
        mycursor.execute(
            "UPDATE bot_control SET extra = ? WHERE guild = ? AND action = ?",
            (filter, ctx.guild.id, "fffilter"),
        )
    else:
        mycursor.execute(
            "INSERT INTO bot_control (guild, action, extra) VALUES (?, ?, ?)",
            (ctx.guild.id, "fffilter", filter),
        )
    mydb.commit()
    mydb.close()
    await ctx.send(f"Set ffmpeg filter to: {filter}")


@bot.command(
        name="filter",
        help="preset audio filters",
        )
async def filter(ctx, *, filter: str = None):
    options = {
            "lowquality": "aresample=8000,lowpass=f=3000,highpass=f=150,volume=1.3,aresample=44100",
            "reverse": "areverse",
            "slow": "asetrate=44100*0.8,aresample=44100",
            "fast": "asetrate=44100*1.25,aresample=44100",
            "bassboost": "bass=g=3",
            "earrape": "acrusher=.1:1:64:0:log",
            "earsex": "acrusher=.1:1:64:0:log,volume=0.3",
            "megabass": "bass=g=10",
    }
    editable = {
        "bass": {"max": 10, "min": -10, "map": "bass=g={}"},  # "bass=g=3"
        "volume": {"max": 5, "min": 0.1, "map": "volume={}"},  # "volume=1.3"
        "speed": {"max": 3, "min": 0.1, "map": "asetrate=44100*{}", "suffix": ",aresample=44100"},  # "asetrate=44100*0.8,aresample=44100"
        "bitrate": {"max": 320000, "min": 1000, "map": "aresample={}", "suffix": ",aresample=44100"},
    }

    s = ""

    if filter is None:
        await ctx.send("Please provide a filter")
        return
    elif filter in ["help", "h"]:
        tmp = ""
        for k in editable:
            tmp += f"{k}: Min: {editable[k]['min']}  -  Max: {editable[k]['max']}\n"
        await ctx.send("Editable filters (name=value):\n" + tmp + "\n")
        tmp = ""
        for k in options:
            tmp += f"{k}\n"
        await ctx.send("Simple filters:\n" + tmp)
        return

    if "add" in filter:
        filter = filter.split("add ")[1]
        s = "add "
    elif "remove" in filter:
        filter = filter.split("remove ")[1]
        s = "remove "

    if filter in ["none", "clear", "stop"]:
        filter = "none"
        await fffilter(ctx, filter=filter)
        return
    elif filter in ["list", "ls"]:
        await fffilter(ctx, filter=filter)
        return
    for f in filter.split(" "):
        if f not in options.keys() and f != "" and "=" not in f:
            await ctx.send(f"Invalid filter '{f}'")
            await ctx.send("Available filters: " + ", ".join(options.keys()))
            return
        elif "=" in f:
            key, value = f.split("=")
            if key not in editable.keys():
                await ctx.send(f"Invalid filter '{f}'")
                await ctx.send("Available filters: " + ", ".join(options.keys()))
                return
            if "." in value:
                try:
                    value = float(value)
                except ValueError:
                    await ctx.send(f"Invalid filter '{f}'")
                    return
            elif value.replace("-", "").isdigit():
                value = int(value)
            else:
                await ctx.send(f"Invalid filter '{f}'")
                return
            if value > editable[key]["max"] or value < editable[key]["min"]:
                await ctx.send(f"Invalid value for '{key}', must be between {editable[key]['min']} and {editable[key]['max']}")
                return
            s += editable[key]["map"].replace("{}", str(value)) + editable[key].get("suffix", "") + ","
        else:
            s += options[f] + ","
    s = s[:-1]
    await fffilter(ctx, filter=s)



bot.run(TOKEN)
