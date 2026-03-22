import os

bind = "0.0.0.0:5000"
workers = 1
threads = 4
timeout = 120

_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)

accesslog = os.path.join(_log_dir, "access.log")
errorlog = os.path.join(_log_dir, "error.log")
