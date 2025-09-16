import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

# Process naming
proc_name = "marketroxo"

# Server mechanics
preload_app = True
daemon = False
pidfile = "logs/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None

def post_fork(server, worker):
    """Called after worker processes are forked"""
    import signal
    from logging_config import setup_4hour_rotation, get_logger
    
    # Setup signal handler para recarregar logging
    def reload_logging(signum, frame):
        setup_4hour_rotation()
        logger = get_logger()
        logger.info(f"Worker {worker.pid} recarregou logging após sinal")
    
    signal.signal(signal.SIGUSR1, reload_logging)
    
    # Setup logging for this worker with process-safe handlers
    setup_4hour_rotation()
    logger = get_logger()
    logger.info(f"Worker {worker.pid} initialized with logging configured")

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal"""
    from logging_config import get_logger
    logger = get_logger()
    logger.info(f"Worker {worker.pid} received INT/QUIT signal")

def on_exit(server):
    """Called when gunicorn is about to exit"""
    from logging_config import get_logger
    logger = get_logger()
    logger.info("Gunicorn server shutting down")