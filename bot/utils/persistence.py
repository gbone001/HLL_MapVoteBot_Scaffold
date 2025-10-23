
import json
import os
from threading import Lock

DATA_DIR = "data"
_lock = Lock()

def load_json(filename, default):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump(default, f, indent=2)
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with _lock:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
