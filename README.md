<h2 align="center"> PoggersBotV2 - Simple, self-hosted music bot with web interface </h2>

<p align="center">
    <img src="https://i.ibb.co/Nyy13p0/poggers.png" alt="poggers">
</p>

---


## Features

- Play music from YouTube, Soundcloud
- Search query or URL
- Supports playlists
- Multi server support
- Simple web interface
- Edit queue (i.e. drag songs) from the web interface

#### Preview Web
![general_webui_example](https://github.com/zigzag1001/poggersbotv2/assets/72932714/39e4dfaa-100c-4414-8fad-2a50c23b233f)
#### Preview Web Features
https://github.com/zigzag1001/poggersbotv2/assets/72932714/f2c2eafc-ca2a-4b77-ba74-9c934166fcdd
#### Preview Basic Text Commands
https://github.com/zigzag1001/poggersbotv2/assets/72932714/d5932a3c-98de-4eeb-8efe-ddf18b155c48



## Installation

1. Install docker
https://docs.docker.com/get-docker/
2. Clone this repository
```bash
git clone https://github.com/zigzag1001/poggersbotv2 && cd poggersbotv2
```
3. Create file named `.env` inside this repo and copy these contents into it:
```env
DISCORD_TOKEN = <your discord bot token>
BASE_URL = http://example.com:7777/
PORT = 7777
```
4. **The discord token is required**, url and port just make the web interface work. If you already have a Discord app skip to 7
5. To create a Discord app and get the token: 

   a. Create app -> https://discord.com/developers/applications?new_application=true

   b. In the left menu click `Bot`, Token will be below the bot's username

   c. If hidden, click reset token, it will show up
6. To get invite link:

    a. In the left menu click `OAuth2` -> `URL generator`

    b. For scopes select `bot`, for permissions select the following:

    `Read Messages/View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`, `Connect`, `Speak`
7. Build and run the docker containers using compose (you might need to run as sudo)
```bash
docker compose up
```

**After a few minutes you should see the bot indicate that it is running**

Notes:
- BASE_URL is the url where the bot is hosted, for example http://example.com, can also be an ip like http://192.168.1.1
- If you are not using 80 or 443 for your port, you need to add the port to BASE_URL, for example http://example.com:7777
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
- In general, the project is a bit wonky, I used it to learn more SQL, HTML/JS/CSS and in general about how to connect a web interface to another thing
