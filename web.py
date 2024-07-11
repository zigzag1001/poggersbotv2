from flask import Flask, render_template, jsonify, make_response, request
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import re
import random
import urllib
import sqlite3
from dotenv import load_dotenv
from youtubesearchpython import SearchVideos

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

load_dotenv()

db_name = "db/bot.db"


def add_to_playlist(url, guild, addnext):
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT id FROM playlist WHERE guild = ? ORDER BY id DESC LIMIT 1",
        (guild,),
    )
    id = mycursor.fetchone()
    if id is None:
        id = 1
    else:
        id = id[0] + 1
    isarr = isinstance(url, list)

    if isarr:
        newarr = [(id + i, guild, x) for i, x in enumerate(url)]

        mycursor.executemany(
            "INSERT INTO playlist (id, guild, url) VALUES (?, ?, ?)", newarr
        )

        mydb.commit()
        mydb.close()
        return

    if addnext:
        mycursor.execute(
            "SELECT id FROM playlist WHERE guild = ? ORDER BY id LIMIT 1",
            (guild,),
        )
        id = mycursor.fetchone()
        if id is None:
            id = 1
        else:
            id = id[0] + 1
        mycursor.execute(
            "UPDATE playlist SET id = id + 1 WHERE id >= ? AND guild = ?",
            (id, guild),
        )
        mydb.commit()

    mycursor.execute(
        "INSERT INTO playlist (id, guild, url) VALUES (?, ?, ?)",
        (id, guild, url),
    )
    mydb.commit()
    mydb.close()


def get_yt_data(urls_list):
    if len(urls_list) == 0:
        return {}
    mydb = sqlite3.connect(db_name)
    mycursor = mydb.cursor()
    # makes one query for all urls
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

    for url in urls_list:
        if url in resultsdict:
            urls_list_data[url] = resultsdict[url]
        elif url.startswith("search://"):
            name = url.split("search://")[1]
            urls_list_data[url] = (name, "search")
        else:
            name = None
            duration = None
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
                if "api-v2" in url:
                    data = os.popen(f"yt-dlp {url} --get-title --get-duration").read().strip().split("\n")
                    name = data[0]
                    duration = data[1]
                    min = int(duration.split(":")[0])
                    sec = int(duration.split(":")[1])
                    duration = str(min * 60 + sec)
                else:
                    name = re.search(r'<meta property="og:title" content="(.*?)">', html).group(1)
                    try:
                        duration = re.search(r'<span aria-hidden="true">(\d+):(\d+)</span>', html)
                        mins = int(duration.group(1))
                        secs = int(duration.group(2))
                        duration = str(mins * 60 + secs)
                    except AttributeError:
                        duration = None

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

            if name is None:
                name = url

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


def rainbowprint(msg) -> None:
    colors = [
        "\033[1;31m",  # red
        "\033[1;32m",  # green
        "\033[1;33m",  # yellow
        "\033[1;34m",  # blue
        "\033[1;35m",  # magenta
        "\033[1;36m",  # cyan
    ]
    reset = "\033[0;0m"
    for i in range(len(msg)):
        print(colors[i % len(colors)] + msg[i], end="")
    print(reset)


@app.route("/")
def display_data():
    return render_template("index.html")


@app.route("/get_data", methods=["GET"])
def get_data():
    guild = request.args.get("guild")
    mydb = sqlite3.connect(db_name)
    cursor = mydb.cursor()
    cursor.execute(
        f"SELECT id, url, guild FROM playlist WHERE guild = {guild} ORDER BY id"
    )
    result = cursor.fetchall()
    mydb.close()
    pllength = len(result)
    playlist = []
    toshow = 10
    playlist_ytdata = get_yt_data([x[1] for x in result[:toshow]])
    for x in result[:toshow]:
        name = playlist_ytdata[x[1]][0]
        duration = playlist_ytdata[x[1]][1]
        if "youtu.be" in x[1] or "youtube.com" in x[1]:
            try:
                thumbnail = f'https://img.youtube.com/vi/{x[1].split("=")[1]}/mqdefault.jpg'
            except IndexError:
                thumbnail = f'https://img.youtube.com/vi/{x[1].split("/")[3]}/mqdefault.jpg'
        elif "soundcloud.com" in x[1]:
            # too slow
            # thumbnail = os.popen(f"yt-dlp {x[1]} --get-thumbnail").read().strip()
            thumbnail = "https://i.imgur.com/8z2e0iM.png"
            thumbnail = "https://edm.com/.image/ar_1:1%2Cc_fill%2Ccs_srgb%2Cq_auto:good%2Cw_1200/MTcyMzYzNDExMzE5OTU3MjQx/soundcloud.png"
        else:
            thumbnail = "https://media.tenor.com/j0qPYTg9a94AAAAi/duck-ducky.gif"
        playlist.append(
            {
                "id": x[0],
                "url": x[1],
                "name": name,
                "thumbnail": thumbnail,
                "guild": str(x[2]),
                "duration": duration,
            }
        )
    response = {
        "playlist": playlist,
        "pllength": pllength,
    }
    response = make_response(jsonify(response))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = 0
    return response


@app.route("/play_song", methods=["POST"])
def play_song():
    data = request.get_json()
    song_id = data.get("id")
    song_url = data.get("url")
    guild = int(data.get("guild"))
    mydb = sqlite3.connect(db_name)
    cursor = mydb.cursor()
    cursor.execute("SELECT id, url FROM playlist ORDER BY id LIMIT 1")
    result = cursor.fetchone()
    if result[0] == song_id and result[1] == song_url:
        return jsonify({"success": True})
    cursor.execute(f"DELETE FROM playlist WHERE id < {song_id}")
    mydb.commit()
    cursor.execute(
        "INSERT INTO bot_control (guild, action) VALUES (?, ?)", (guild, "skip")
    )
    mydb.commit()
    mydb.close()
    return jsonify({"success": True})


@app.route("/delete_song", methods=["POST"])
def delete_song():
    data = request.get_json()
    song_id = data.get("id")
    url = data.get("url")
    guild = int(data.get("guild"))
    mydb = sqlite3.connect(db_name)
    cursor = mydb.cursor()
    cursor.execute("SELECT guild, id, url FROM playlist ORDER BY id LIMIT 1")
    result = cursor.fetchone()
    if result[1] == song_id and result[2] == url and result[0] == guild:
        print("skipping")
        cursor.execute(
            f"INSERT INTO bot_control (guild, action) VALUES ('{result[0]}', 'skip')"
        )
    cursor.execute(f"DELETE FROM playlist WHERE id = {song_id} AND url = '{url}'")
    mydb.commit()
    mydb.close()
    return jsonify({"success": True})


@app.route("/skip_song", methods=["POST"])
def skip_song():
    data = request.get_json()
    guild = int(data.get("guild"))
    mydb = sqlite3.connect(db_name)
    cursor = mydb.cursor()
    cursor.execute(
        f"INSERT INTO bot_control (guild, action) VALUES (?, ?)", (guild, "skip")
    )
    mydb.commit()
    cursor.execute(f"DELETE FROM playlist WHERE guild = {guild} ORDER BY id LIMIT 1")
    mydb.commit()
    mydb.close()
    return jsonify({"success": True})


@app.route("/shuffle", methods=["POST"])
def shuffle():
    data = request.get_json()
    guild = int(data.get("guild"))
    mydb = sqlite3.connect(db_name)
    cursor = mydb.cursor()
    cursor.execute(
        f"SELECT url, id FROM playlist WHERE guild = {guild} ORDER BY id"
    )
    result = cursor.fetchall()

    urls_list = [x[0] for x in result]

    currentid = result[0][1]

    del urls_list[0]

    random.shuffle(urls_list)

    cursor.execute(
        "DELETE FROM playlist WHERE guild = ? AND id > ?", (guild, currentid)
    )

    mydb.commit()
    mydb.close()

    add_to_playlist(urls_list, guild, False)

    return jsonify({"success": True})


@app.route("/loop", methods=["POST"])
def loop():
    data = request.get_json()
    guild = int(data.get("guild"))
    mydb = sqlite3.connect(db_name)
    cursor = mydb.cursor()
    cursor.execute(
        f"SELECT action FROM bot_control WHERE guild = {guild} AND action = 'loop'"
    )
    result = cursor.fetchone()
    print(result)
    if result:
        print("removing loop")
        cursor.execute(
            f"DELETE FROM bot_control WHERE guild = {guild} AND action = 'loop'"
        )
        mydb.commit()
        return jsonify({"success": True, "looping": False})
    print("adding loop")
    cursor.execute(
        f"INSERT INTO bot_control (guild, action) VALUES (?, ?)", (guild, "loop")
    )
    mydb.commit()
    mydb.close()
    return jsonify({"success": True, "looping": True})


# recievs updated list from web interface, if order is different, update database
@app.route("/update_list", methods=["POST"])
def update_list():
    data = request.get_json()
    guild = int(data[0].get("guild"))
    mydb = sqlite3.connect(db_name)
    cursor = mydb.cursor()
    unsorted_ids = []
    for song in data:
        id = int(song.get("id"))
        unsorted_ids.append(id)
    sorted_ids = sorted(unsorted_ids)
    if sorted_ids[0] != unsorted_ids[0]:
        cursor.execute(
            f"INSERT INTO bot_control (guild, action) VALUES (?, ?)", (guild, "skip")
        )
        mydb.commit()
    for i in range(len(sorted_ids)):
        cursor.execute(
            f"UPDATE playlist SET id = {sorted_ids[i]} WHERE url = '{data[i].get('url')}' AND guild = {guild}"
        )
        mydb.commit()
    mydb.close()
    return jsonify({"success": True})


@app.route("/add_song", methods=["POST"])
def add_song():
    data = request.get_json()
    search = data.get("addurl")
    guild = int(data.get("guild"))
    addnext = data.get("addnext")
    results = None
    is_playlist = False
    is_url = False

    # Check if search is a url using regex
    protocol = r"(https:\/\/www\.|http:\/\/www\.|https:\/\/|http:\/\/)?"
    domain = r"[a-zA-Z]{2,}(\.[a-zA-Z]{2,})(\.[a-zA-Z]{2,})?"
    path = r"\/[a-zA-Z0-9]{2,}"
    subdomain = r"((https:\/\/www\.|http:\/\/www\.|https:\/\/|http:\/\/)?[a-zA-Z]{2,}(\.[a-zA-Z]{2,})(\.[a-zA-Z]{2,})?)"
    ip_domain = r"(https:\/\/www\.|http:\/\/www\.|https:\/\/|http:\/\/)?[a-zA-Z0-9]{2,}\.[a-zA-Z0-9]{2,}\.[a-zA-Z0-9]{2,}(\.[a-zA-Z0-9]{2,})?"

    final_regex = re.compile(f"{protocol}({domain}{path}|{subdomain}|{ip_domain})")
    if re.match(final_regex, search):
        if "playlist?list=" in search or "/sets/" in search.split("?")[0]:
            is_playlist = True
            plisturl = search
            if "youtube.com" in search or "youtu.be" in search:
                if "&list=" in search:
                    plistid = search.split("&list=")[1]
                elif "playlist?list=" in search:
                    plistid = search.split("playlist?list=")[1]

                if "&" in plistid:
                    plistid = plistid.split("&")[0]

                plisturl = f"https://www.youtube.com/playlist?list={plistid}"
            ytplaylist = (
                str(os.popen(f"yt-dlp {plisturl} --flat-playlist --get-url").read())
                .strip()
                .split("\n")
            )
            add_to_playlist(ytplaylist, guild, addnext)
            return jsonify({"success": True, "is_playlist": is_playlist, "is_url": is_url})
        elif "youtube.com" in search or "youtu.be" in search or "soundcloud.com" in search:
            is_url = True
            add_to_playlist(search, guild, addnext)
            return jsonify({"success": True, "is_playlist": is_playlist, "is_url": is_url})
        else:
            return jsonify({"success": False, "error": "Invalid URL"})
    else:
        search = SearchVideos(search, offset=1, mode="json", max_results=5)
        info = search.result()
        try:
            info = eval(info)
        except TypeError:
            return jsonify({"success": False, "error": "No results found / search error"})
        results = []
        num_results = 5 if len(info["search_result"]) > 5 else len(info["search_result"])
        for x in range(len(info["search_result"])):
            results.append(
                {
                    "url": info["search_result"][x]["link"],
                    "title": info["search_result"][x]["title"],
                    "duration": info["search_result"][x]["duration"],
                }
            )
    return jsonify(
        {
            "success": True,
            "results": results,
            "is_playlist": is_playlist,
            "is_url": is_url,
        }
    )


port = int(os.getenv("PORT"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
