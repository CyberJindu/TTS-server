import os
import multiprocessing

# Get port from environment
port = os.environ.get('PORT', '5001')

# Bind to port
bind = f"0.0.0.0:{port}"

# Number of worker processes
workers = multiprocessing.cpu_count() * 2 + 1

# Worker type
worker_class = "sync"

# Timeout
timeout = 120

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Preload app
preload_app = True

# Max requests
max_requests = 1000
max_requests_jitter = 100
