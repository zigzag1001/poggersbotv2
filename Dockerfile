# bot.py

# Python 3.11
FROM python:3.11

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the dependencies
RUN pip install -r requirements.txt

# Set environment variables
ENV DISCORD_TOKEN=your_token
ENV MYSQL_ROOT_PASSWORD=root_password
ENV MYSQL_DATABASE=bot_db
ENV MYSQL_USER=bot_user
ENV MYSQL_PASSWORD=bot_password
ENV MYSQL_HOST=localhost
ENV PORT=7777
ENV BASE_URL=http://localhost:7777

# Port
EXPOSE 7777

# Run the app
CMD ["python", "bot.py"]


# Flask web.py

# Pull the Python 3.11 image
FROM python:3.11

# Run
CMD ["python", "web.py"]


# MariaDB

# Pull the MariaDB image
FROM mariadb:latest
