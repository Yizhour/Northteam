import json
import os
import schedule
import threading
import time
import uuid
from contextlib import contextmanager

from .config import LOG_DIR, ensure_directories
from .logging_utils import append_log
from .manuscript_logic import ManuscriptReminder
from .storage import load_config


SCHEDULER_LOCK_FILE = LOG_DIR / "scheduler.lock"
TASK_LOCK_FILE = LOG_DIR / "task-execution.lock"
SCHEDULER_LOCK_TTL_SECONDS = 30
TASK_LOCK_TTL_SECONDS = 60 * 60 * 2
CONFIG_REFRESH_SECONDS = 5
HEARTBEAT_SECONDS = 5


class CrossProcessLock:
    def __init__(self, path, ttl_seconds):
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.token = f"{os.getpid()}:{uuid.uuid4()}"
        self.acquired = False

    def acquire(self):
        ensure_directories()
        now = time.time()
        payload = json.dumps({"pid": os.getpid(), "token": self.token, "updated_at": now})
        for _ in range(2):
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                self.acquired = True
                return True
            except FileExistsError:
                if not self._is_stale(now):
                    return False
                try:
                    self.path.unlink()
                except OSError:
                    return False
        return False

    def heartbeat(self):
        if not self.acquired or not self.is_owner():
            self.acquired = False
            return False
        try:
            self.path.write_text(json.dumps({"pid": os.getpid(), "token": self.token, "updated_at": time.time()}), encoding="utf-8")
            return True
        except OSError:
            self.acquired = False
            return False

    def is_owner(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return False
        return data.get("token") == self.token

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
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            updated_at = float(data.get("updated_at") or 0)
        except Exception:
            try:
                updated_at = self.path.stat().st_mtime
            except OSError:
                return True
        return now - updated_at > self.ttl_seconds


@contextmanager
def task_execution_lock():
    lock = CrossProcessLock(TASK_LOCK_FILE, TASK_LOCK_TTL_SECONDS)
    if not lock.acquire():
        yield False
        return
    try:
        yield True
    finally:
        lock.release()


def run_with_task_lock(callback, busy_message="底稿报送提醒任务正在执行，请稍后再试。"):
    with task_execution_lock() as acquired:
        if not acquired:
            append_log(busy_message)
            return None
        return callback()


def config_fingerprint(config):
    watched = {
        "weekly_enabled": config.get("weekly_enabled", True),
        "weekly_time": config.get("weekly_time", "09:00"),
        "schedule_day": config.get("schedule_day", "Monday"),
        "daily_enabled": config.get("daily_enabled", False),
        "daily_time": config.get("daily_time", "09:00"),
    }
    return json.dumps(watched, ensure_ascii=False, sort_keys=True)


class SchedulerService:
    def __init__(self):
        self._thread = None
        self._monitor_thread = None
        self._active = False
        self._lock = threading.Lock()
        self._scheduler_lock = None
        self._config_fingerprint = None
        self._last_config_check = 0.0
        self._last_heartbeat = 0.0

    def start(self):
        if self._thread and self._thread.is_alive():
            return True
        scheduler_lock = CrossProcessLock(SCHEDULER_LOCK_FILE, SCHEDULER_LOCK_TTL_SECONDS)
        if not scheduler_lock.acquire():
            return False
        self._scheduler_lock = scheduler_lock
        self._active = True
        self.schedule_jobs()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        append_log("底稿报送提醒调度器已启动。")
        return True

    def start_monitor(self):
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self):
        while True:
            if self._thread and self._thread.is_alive():
                return
            if self.start():
                return
            time.sleep(10)

    def restart(self):
        if self._scheduler_lock and self._scheduler_lock.acquired:
            self.schedule_jobs()

    def _run_loop(self):
        while self._active:
            now = time.monotonic()
            if now - self._last_heartbeat >= HEARTBEAT_SECONDS:
                self._last_heartbeat = now
                if not self._scheduler_lock or not self._scheduler_lock.heartbeat():
                    append_log("底稿报送提醒调度器锁已失效，当前调度线程停止。")
                    self._active = False
                    break
            if now - self._last_config_check >= CONFIG_REFRESH_SECONDS:
                self._last_config_check = now
                self.refresh_if_config_changed()
            schedule.run_pending()
            time.sleep(1)

    def refresh_if_config_changed(self):
        config = load_config()
        fingerprint = config_fingerprint(config)
        if fingerprint != self._config_fingerprint:
            self.schedule_jobs(config=config, fingerprint=fingerprint)

    def schedule_jobs(self, config=None, fingerprint=None):
        with self._lock:
            schedule.clear("manuscriptreminder")
            config = config or load_config()
            if config.get("weekly_enabled", True):
                job_creator = getattr(schedule.every(), str(config.get("schedule_day", "Monday")).lower(), None)
                if job_creator:
                    job_creator.at(config.get("weekly_time", "09:00")).do(self.run_weekly).tag("manuscriptreminder")
            if config.get("daily_enabled", False):
                schedule.every().day.at(config.get("daily_time", "09:00")).do(self.run_daily).tag("manuscriptreminder")
            self._config_fingerprint = fingerprint or config_fingerprint(config)

    def run_weekly(self):
        return run_with_task_lock(lambda: ManuscriptReminder(load_config()).run_weekly_check())

    def run_daily(self):
        return run_with_task_lock(lambda: ManuscriptReminder(load_config()).run_daily_check())


scheduler_service = SchedulerService()
