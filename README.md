<h2 align="center"> PoggersBotV2 - Simple, self-hosted music bot with web interface </h2>

<p align="center">
    <img src="https://i.ibb.co/Nyy13p0/poggers.png" alt="poggers">
</p>

---


#### Features

- Play music from YouTube
- Search query or URL
- Supports playlists
- Multi server support
- Simple web interface
- Edit queue from web interface

#### Installation

1. Install a mysql server, for example [MariaDB](https://pimylifeup.com/raspberry-pi-mysql/) (that tutorial is for raspberry pi, but it shows the setup process pretty well)
2. Create a discord app to get your token, [tutorial](https://discordpy.readthedocs.io/en/stable/discord.html)
2. Install FFMPEG and python, I use 3.11, havent tested with others
3. Clone this repository
```
git clone https://github.com/zigzag1001/poggersbotv2 && cd poggersbotv2
```
4. Install dependencies
```
pip install -r requirements.txt
```
5. Create .env file with following contents:
```
DISCORD_TOKEN = <your discord bot token>
MYSQL_HOST = <your mysql host>
MYSQL_USER = <your mysql user>
MYSQL_PASSWORD = <your mysql password>
MYSQL_DATABASE = <your mysql database>
BASE_URL = <your base url>
PORT = <your port>
```
6. Hope and pray (ive got no idea how / if this works on other machines)
7. Run `start_all.sh` (i will probably add a windows version of this later)

Notes:
- MYSQL_HOST is usually `localhost`
- BASE_URL is the url where the bot is hosted, for example http://example.com, can also be an ip like http://192.168.1.1
- If you are not using 80 or 443 for your port, you need to add the port to BASE_URL, for example http://example.com:8080
- For other people to access the web interface, you need to port forward the port you set in .env

#### Usage

Bot uses prefix `r;`, for example `r;play <query>`

Use `r;help` to get a list of commands

Some commands also have shorter aliases
```
r;play - r;p
r;queue - r;q
r;shuffle - r;sh
r;skip - r;s
r;loop - r;l
r;web - r;w
```

For `play` you can enter either search, url or playlist url

For `shuffle` you can optionally enter a playlist url, it will shuffle the playlist before adding to queue

For `queue` you can optionally enter a number, it will show that many songs from the queue, default is 10

### More notes
- Setup is kinda complicated, I will try to make it easier in the future
- In code documentation to be added later
- In general, the project is a bit wonky, I used it to learn more SQL, HTML/JS/CSS and in general about how to connect a web interface to another thing
