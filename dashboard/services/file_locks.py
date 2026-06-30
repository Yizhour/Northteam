import json
import os
import time
import uuid
from contextlib import contextmanager

from django.conf import settings


RUNTIME_DIR = settings.BASE_DIR / 'runtime'


class CrossProcessFileLock:
    def __init__(self, name, ttl_seconds):
        self.path = RUNTIME_DIR / f'{name}.lock'
        self.ttl_seconds = ttl_seconds
        self.token = f'{os.getpid()}:{uuid.uuid4()}'
        self.acquired = False

    def acquire(self):
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        now = time.time()
        payload = json.dumps({'pid': os.getpid(), 'token': self.token, 'updated_at': now})
        for _ in range(2):
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                    handle.write(payload)
                self.acquired = True
                return True
            except FileExistsError:
                if not self._is_stale(now):
                    return False
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    return False
        return False

    def heartbeat(self):
        if not self.acquired or not self.is_owner():
            self.acquired = False
            return False
        payload = json.dumps({'pid': os.getpid(), 'token': self.token, 'updated_at': time.time()})
        try:
            self.path.write_text(payload, encoding='utf-8')
            return True
        except OSError:
            self.acquired = False
            return False

    def is_owner(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8') or '{}')
        except Exception:
            return False
        return data.get('token') == self.token

    def release(self):
        if not self.acquired:
            return
        try:
            if self.is_owner():
                self.path.unlink(missing_ok=True)
        except OSError:
            pass
        finally:
            self.acquired = False

    def _is_stale(self, now):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8') or '{}')
            updated_at = float(data.get('updated_at') or 0)
        except Exception:
            try:
                updated_at = self.path.stat().st_mtime
            except OSError:
                return True
        return now - updated_at > self.ttl_seconds


@contextmanager
def file_lock(name, ttl_seconds):
    lock = CrossProcessFileLock(name, ttl_seconds)
    if not lock.acquire():
        yield False
        return
    try:
        yield True
    finally:
        lock.release()
