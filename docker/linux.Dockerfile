# Dockerfile (e.g., in your `docker/` folder)
FROM python:3.9-slim-buster # Or another Python 3.x Linux image

# Set the working directory inside the container
WORKDIR /app

# Copy your project files into the container.
# The build context '.' will be your project root.
COPY . /app 

# Install Python dependencies (including pyinstaller)
RUN pip install --no-cache-dir -r /app/requirements.txt 

# Command to build the Linux executable using PyInstaller
# This will be executed when you `docker run` the container.
CMD ["pyinstaller", "--onefile", "--noconsole", "--name", "MarketRoxoMonitor", "--add-data", ".env:.", "/app/main.py"]