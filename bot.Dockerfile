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

# Copy the current directory contents into the container at /app
# COPY . /app

ADD . /app

# Run the app
CMD ["python", "-u", "bot.py"]
