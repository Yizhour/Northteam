import os
import random
import sys
import threading
import time
from datetime import datetime, time as datetime_time, timedelta

from django.utils import timezone

from dashboard.services.file_locks import CrossProcessFileLock
from dashboard.services.market_yields import fetch_recent_market_yields


SCHEDULER_LOCK_TTL_SECONDS = 60
HEARTBEAT_SECONDS = 10
MONITOR_SECONDS = 30
LOOP_SECONDS = 20


class MarketYieldScheduler:
    def __init__(self):
        self._thread = None
        self._monitor_thread = None
        self._lock = None
        self._active = False
        self._thread_lock = threading.Lock()
        self._last_heartbeat = 0.0
        self._run_date = None
        self._target_run_at = None

    def start(self):
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return True
            scheduler_lock = CrossProcessFileLock('market-yields-scheduler', SCHEDULER_LOCK_TTL_SECONDS)
            if not scheduler_lock.acquire():
                return False
            self._lock = scheduler_lock
            self._active = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return True

    def start_monitor(self):
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        self._active = False
        if self._lock:
            self._lock.release()
            self._lock = None

    def _monitor_loop(self):
        while True:
            if self._thread and self._thread.is_alive():
                return
            if self.start():
                return
            time.sleep(MONITOR_SECONDS)

    def _run_loop(self):
        while self._active:
            now_monotonic = time.monotonic()
            if now_monotonic - self._last_heartbeat >= HEARTBEAT_SECONDS:
                self._last_heartbeat = now_monotonic
                if not self._lock or not self._lock.heartbeat():
                    self._active = False
                    break

            self._run_if_due()
            time.sleep(LOOP_SECONDS)

    def _run_if_due(self):
        now = timezone.localtime()
        today = now.date()
        if today.weekday() >= 5:
            self._target_run_at = None
            return
        if self._run_date == today:
            return
        if self._target_run_at is None or self._target_run_at.date() != today:
            base = timezone.make_aware(datetime.combine(today, datetime_time(19, 0)))
            self._target_run_at = base + timedelta(minutes=random.randint(0, 10))
        if now >= self._target_run_at:
            try:
                fetch_recent_market_yields()
            finally:
                self._run_date = today


def should_start_market_yield_scheduler():
    management_commands = {'migrate', 'makemigrations', 'collectstatic', 'test'}
    if any(command in sys.argv for command in management_commands):
        return False
    flag = os.environ.get('ENABLE_MARKET_YIELD_SCHEDULER', os.environ.get('ENABLE_SCHEDULER', '1'))
    return flag.lower() in {'1', 'true', 'yes', 'on'}


market_yield_scheduler = MarketYieldScheduler()
