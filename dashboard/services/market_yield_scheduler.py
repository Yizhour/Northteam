import os
import random
import sys
import threading
import time
from datetime import datetime, time as datetime_time, timedelta

from django.utils import timezone

from dashboard.services.file_locks import CrossProcessFileLock
from dashboard.services.market_yield_refresh import run_market_yield_refresh


SCHEDULER_LOCK_TTL_SECONDS = 60
HEARTBEAT_SECONDS = 10
MONITOR_SECONDS = 30
LOOP_SECONDS = 20
FETCH_WINDOWS = (
    (datetime_time(17, 40), datetime_time(17, 45)),
)
MAX_FETCH_ATTEMPTS = 2
RETRY_AFTER_FAILURE = timedelta(minutes=10)


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
        self._attempt_date = None
        self._attempt_index = 0

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
        if self._run_date == today:
            return
        if self._attempt_date != today:
            self._attempt_date = today
            self._attempt_index = 0
            self._target_run_at = None
        if self._attempt_index >= MAX_FETCH_ATTEMPTS:
            return
        if self._target_run_at is None or self._target_run_at.date() != today:
            self._target_run_at = (
                self._random_time_in_window(today)
                if self._attempt_index == 0
                else now + RETRY_AFTER_FAILURE
            )
        if now >= self._target_run_at:
            result = run_market_yield_refresh(trigger='auto', requested_by='scheduler')
            if result.get('ok'):
                self._run_date = today
                return
            self._attempt_index += 1
            self._target_run_at = now + RETRY_AFTER_FAILURE if self._attempt_index < MAX_FETCH_ATTEMPTS else None

    def _random_time_in_window(self, day):
        start_time, end_time = FETCH_WINDOWS[0]
        start_at = timezone.make_aware(datetime.combine(day, start_time))
        end_at = timezone.make_aware(datetime.combine(day, end_time))
        seconds = max(0, int((end_at - start_at).total_seconds()))
        return start_at + timedelta(seconds=random.randint(0, seconds))


def should_start_market_yield_scheduler():
    management_commands = {'migrate', 'makemigrations', 'collectstatic', 'test'}
    if any(command in sys.argv for command in management_commands):
        return False
    flag = os.environ.get('ENABLE_MARKET_YIELD_SCHEDULER', os.environ.get('ENABLE_SCHEDULER', '1'))
    return flag.lower() in {'1', 'true', 'yes', 'on'}


market_yield_scheduler = MarketYieldScheduler()
