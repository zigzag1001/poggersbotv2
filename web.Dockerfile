# Flask web.py

# Pull the Python 3.11 image
FROM python:3.11

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run web.py when the container launches
CMD ["python", "-u", "web.py"]
