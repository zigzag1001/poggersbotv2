import schedule
import time
import os
import subprocess
import psutil

def start_bot():
    bot = subprocess.Popen(["python3.11", "bottwo.py"])
    print('started bot with pid', bot.pid)

def restart_bot():
    print("its time!")
    # Find the process ID (PID) of the previous instance of the bot
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if 'python3.11' in proc.info['name'] and 'bottwo.py' in proc.info['cmdline']:
            os.kill(proc.info['pid'], 2)
            print('killed ', proc.info['pid'], ' aka ', proc.info['name'])
            break

    start_bot()

# Schedule the restart every day at 6 am
schedule.every().day.at("06:00").do(restart_bot)

# Start the first instance
start_bot()

while True:
    schedule.run_pending()
    bot_alive = False
    for proc in psutil.process_iter(['name', 'cmdline']):
        if 'python3.11' in proc.info['name'] and 'bottwo.py' in proc.info['cmdline']:
            bot_alive = True
            break
    if bot_alive == False:
        start_bot()

    time.sleep(1)
