# Use official Python 3.12 image
FROM python:3.12-bookworm

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git build-essential cmake flex bison \
    libelf-dev zlib1g-dev libfl-dev python3-distutils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
CMD ["python", "server.py"]

# docker build -t my-python-app .
# docker run -p 5000:5000 -v $(pwd):/app my-python-app
# docker run -p 5000:5000 --env-file .env my-python-app