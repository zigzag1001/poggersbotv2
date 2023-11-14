# bot.py

# Python 3.11
FROM python:3.11

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the app
CMD ["python", "-u", "bot.py"]
