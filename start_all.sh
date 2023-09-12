#!/bin/bash

# Function to handle Ctrl+C
function ctrl_c() {
    echo "Terminating bot and web server..."
    pkill -P $$  # Terminate child processes
    exit 1
}

# Set up Ctrl+C handler
trap ctrl_c INT

# Start the bot
python3.11 bot.py &

# Store the PID of the bot process
bot_pid=$!

# Start the web server
python3.11 web.py &

# Store the PID of the web server process
web_pid=$!

echo "Started bot and web server"

# Wait for Ctrl+C
wait

# Cleanup after Ctrl+C
kill -9 $bot_pid $web_pid  # Terminate both processes forcefully

exit 0

