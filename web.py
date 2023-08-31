from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, make_response, request
import os
import re
import random
import urllib
import mysql.connector

load_dotenv()

app = Flask(__name__)


@app.route("/")
def display_data():
    return render_template("index.html")


@app.route("/get_data")
def get_data():
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
    cursor = mydb.cursor()
    cursor.execute(
        f"SELECT id, url, name, guild, duration FROM playlist ORDER BY id LIMIT 10"
    )
    result = cursor.fetchall()
    playlist = []
    for x in result:
        if x[2] == None or x[4] == None:
            response = urllib.request.urlopen(x[1])
            html = response.read().decode("utf-8")
            name = re.search("<title>(.*)</title>", html).group(1).split("- YouTube")[0]
            duration = re.search(r'"lengthSeconds":"(.*?)"', html).group(1)
            mins = str(int(duration) // 60)
            secs = f"{int(duration) % 60 : 03d}"
            duration_minsec = f"{mins}:{secs.strip()}"
            cursor.execute(
                "UPDATE playlist SET name = %s, duration = %s WHERE url = %s",
                (name, duration_minsec, x[1]),
            )
            mydb.commit()
        else:
            name = x[2]
        try:
            thumbnail = f'https://img.youtube.com/vi/{x[1].split("=")[1]}/mqdefault.jpg'
        except:
            thumbnail = f'https://img.youtube.com/vi/{x[1].split("/")[3]}/mqdefault.jpg'
        playlist.append(
            {
                "id": x[0],
                "url": x[1],
                "name": name,
                "thumbnail": thumbnail,
                "guild": str(x[3]),
                "duration": x[4],
            }
        )
    # print(playlist)
    response = make_response(jsonify(playlist))
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
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
    cursor = mydb.cursor()
    cursor.execute(f"SELECT id, url FROM playlist ORDER BY id LIMIT 1")
    result = cursor.fetchone()
    if result[0] == song_id and result[1] == song_url:
        print("not skipping")
        return jsonify({"success": True})
    # delete songs between smallest and song_id
    cursor.execute(f"DELETE FROM playlist WHERE id < {song_id}")
    mydb.commit()
    cursor.execute(
        "INSERT INTO bot_control (guild, action) VALUES (%s, %s)", (guild, "skip")
    )
    mydb.commit()
    return jsonify({"success": True})


@app.route("/delete_song", methods=["POST"])
def delete_song():
    data = request.get_json()
    song_id = data.get("id")
    url = data.get("url")
    guild = int(data.get("guild"))
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
    cursor = mydb.cursor()
    cursor.execute(f"SELECT guild, id, url FROM playlist ORDER BY id LIMIT 1")
    result = cursor.fetchone()
    if result[1] == song_id and result[2] == url and result[0] == guild:
        print("skipping")
        cursor.execute(
            f"INSERT INTO bot_control (guild, action) VALUES ('{result[0]}', 'skip')"
        )
    cursor.execute(f"DELETE FROM playlist WHERE id = {song_id} AND url = '{url}'")
    mydb.commit()
    return jsonify({"success": True})


@app.route("/skip_song", methods=["POST"])
def skip_song():
    data = request.get_json()
    guild = int(data.get("guild"))
    print(guild)
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
    cursor = mydb.cursor()
    cursor.execute(
        f"INSERT INTO bot_control (guild, action) VALUES (%s, %s)", (guild, "skip")
    )
    mydb.commit()
    cursor.execute(f"DELETE FROM playlist WHERE guild = {guild} ORDER BY id LIMIT 1")
    mydb.commit()
    return jsonify({"success": True})


@app.route("/playpause", methods=["POST"])
def play_pause():
    data = request.get_json()
    guild = int(data.get("guild"))
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
    cursor = mydb.cursor()
    cursor.execute(
        f"INSERT INTO bot_control (guild, action) VALUES (%s, %s)", (guild, "playpause")
    )
    mydb.commit()
    print("playpause")
    return jsonify({"success": True})


@app.route("/shuffle", methods=["POST"])
def shuffle():
    data = request.get_json()
    guild = int(data.get("guild"))
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
    cursor = mydb.cursor()
    cursor.execute(f"SELECT id, url FROM playlist WHERE guild = {guild} ORDER BY id")
    result = cursor.fetchall()
    ids = []
    urls = []
    for x in result:
        ids.append(x[0])
        urls.append(x[1])
    currentid = ids.pop(0)
    currenturl = urls.pop(0)
    random.shuffle(ids)
    for i in range(len(ids)):
        cursor.execute(f"UPDATE playlist SET id = {ids[i]} WHERE url = '{urls[i]}'")
        mydb.commit()
    return jsonify({"success": True})


@app.route("/loop", methods=["POST"])
def loop():
    data = request.get_json()
    guild = int(data.get("guild"))
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
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
        f"INSERT INTO bot_control (guild, action) VALUES (%s, %s)", (guild, "loop")
    )
    mydb.commit()
    return jsonify({"success": True, "looping": True})


# recievs updated list from web interface, if order is different, update database
@app.route("/update_list", methods=["POST"])
def update_list():
    data = request.get_json()
    guild = int(data[0].get("guild"))
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
    cursor = mydb.cursor()
    unsorted_ids = []
    for song in data:
        id = int(song.get("id"))
        unsorted_ids.append(id)
    sorted_ids = sorted(unsorted_ids)
    if sorted_ids[0] != unsorted_ids[0]:
        cursor.execute(
            f"INSERT INTO bot_control (guild, action) VALUES (%s, %s)", (guild, "skip")
        )
        mydb.commit()
    for i in range(len(sorted_ids)):
        cursor.execute(
            f"UPDATE playlist SET id = {sorted_ids[i]} WHERE url = '{data[i].get('url')}' AND guild = {guild}"
        )
        mydb.commit()

    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7777)
