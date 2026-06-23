import multiprocessing

# Bind to port
bind = "0.0.0.0:5001"

# Number of worker processes
workers = multiprocessing.cpu_count() * 2 + 1

# Worker type (sync, gevent, etc.)
worker_class = "sync"

# Timeout in seconds
timeout = 120

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Preload app for better performance
preload_app = True

# Max requests before worker restart (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 100
