from collections import deque
from datetime import datetime
from threading import Lock

_lock = Lock()
_logs = deque(maxlen=2000)


def append_log(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    with _lock:
        _logs.append(line)
    return line


def read_logs(limit=2000):
    with _lock:
        lines = list(_logs)
    if limit <= 0:
        return lines
    return lines[-limit:]


def clear_logs():
    with _lock:
        _logs.clear()
