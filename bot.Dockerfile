# bot.py

# Python 3.11
FROM python:3.11

# Set the working directory to /app
WORKDIR /app

ADD ./requirements.txt /app/requirements.txt

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt
# RUN pip install --no-cache-dir git+https://github.com/Rapptz/discord.py@398bdbecd97eb2e05f91ddbf121ff0d200c039b5

# Always try to pull latest yt-dlp due te constant changes
ARG CACHEBUST=1
RUN echo "$CACHEBUST"
RUN pip install git+https://github.com/yt-dlp/yt-dlp.git

# Copy the current directory contents into the container at /app
# COPY . /app

ADD . /app

# Run the app
CMD ["python", "-u", "bot.py"]
