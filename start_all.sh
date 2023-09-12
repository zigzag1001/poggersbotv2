#!/bin/bash

# Start all services

# Start the bot
python3.11 bot.py &

# Start the web server
python3.11 web.py &

echo "Started bot and web server"

exit 0
