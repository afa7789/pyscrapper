# Start from a suitable Python base image for your Windows build environment
FROM python:3.9-slim-buster # Or another Python 3.x Linux image

# Install Wine and MinGW-w64 for Windows cross-compilation
# Ensure these tools are available for PyInstaller to target Windows
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y wine-stable wine32 mingw-w64 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set up environment for PyInstaller to use Wine
ENV WINEPREFIX /home/user/.wine
ENV PATH "$PATH:/usr/bin" # Ensure wine and mingw are in PATH

# Set the working directory inside the container
WORKDIR /app

# Copy your project files into the container.
# Since the build context is your project root ('.'), 
# 'COPY .' will copy everything from the project root into /app.
COPY . /app 

# Install Python dependencies (including pyinstaller)
RUN pip install --no-cache-dir -r /app/requirements.txt # Specify full path for requirements.txt

# Command to build the Windows executable using PyInstaller and Wine
# Note: You'll run this command after the Docker image is built and when you run the container.
# This assumes your main script is directly in /app after the COPY.
CMD ["wine", "pyinstaller", "--onefile", "--windowed", "--name", "MarketRoxoMonitor", "--add-data", ".env;.", "/app/main.py"]