import schedule
import threading
import time
from datetime import datetime

from .bond_logic import BondReminder
from .customer_logic import check_birthday_jobs
from .storage import load_config, save_config


class SchedulerService:
    def __init__(self):
        self._thread = None
        self._active = False
        self._lock = threading.Lock()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._active = True
        self.schedule_jobs()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._active = False
        schedule.clear()

    def restart(self):
        self.schedule_jobs()

    def _run_loop(self):
        while self._active:
            schedule.run_pending()
            time.sleep(1)

    def schedule_jobs(self):
        with self._lock:
            schedule.clear()
            config = load_config()
            weekly_time = config.get("weekly_time") or config.get("common_time", "09:00")
            daily_time = config.get("daily_time") or config.get("common_time", "09:00")

            if config.get("weekly_enabled", True):
                day = config.get("schedule_day", "Monday")
                job_creator = getattr(schedule.every(), day.lower(), None)
                if job_creator:
                    job_creator.at(weekly_time).do(self.run_weekly)

            if config.get("daily_enabled", False):
                schedule.every().day.at(daily_time).do(self.run_daily)

            schedule.every().minute.do(check_birthday_jobs)

            for task in config.get("custom_tasks", []):
                if not task.get("enabled", True) or task.get("executed", False):
                    continue
                time_config = task.get("time_config", {})
                time_type = time_config.get("type", "once")
                task_time = time_config.get("time", "00:00")
                if time_type == "once":
                    target_date = time_config.get("date")
                    if target_date:
                        schedule.every().day.at(task_time).do(self.check_and_run_once, task, target_date)
                elif time_type == "weekly":
                    weekday_map = {
                        "周一": "monday",
                        "周二": "tuesday",
                        "周三": "wednesday",
                        "周四": "thursday",
                        "周五": "friday",
                        "周六": "saturday",
                        "周日": "sunday",
                    }
                    for weekday in time_config.get("weekdays", []):
                        en_weekday = weekday_map.get(weekday)
                        job_creator = getattr(schedule.every(), en_weekday, None) if en_weekday else None
                        if job_creator:
                            job_creator.at(task_time).do(self.run_custom_task, task)
                elif time_type == "daily":
                    schedule.every().day.at(task_time).do(self.run_custom_task, task)

    def run_weekly(self):
        reminder = BondReminder(load_config())
        return reminder.run_weekly_check()

    def run_daily(self):
        reminder = BondReminder(load_config())
        return reminder.run_daily_check()

    def run_custom_task(self, task):
        reminder = BondReminder(load_config())
        reminder.run_custom_task(task)

    def check_and_run_once(self, task, target_date):
        current_date = datetime.now().strftime("%Y-%m-%d")
        if task.get("executed", False):
            return schedule.CancelJob
        if current_date == target_date:
            self.run_custom_task(task)
            config = load_config()
            for saved_task in config.get("custom_tasks", []):
                if saved_task.get("name") == task.get("name") and saved_task.get("time_config") == task.get("time_config"):
                    saved_task["executed"] = True
                    saved_task["enabled"] = False
                    break
            save_config(config)
            return schedule.CancelJob
        if current_date > target_date:
            return schedule.CancelJob
        return None


scheduler_service = SchedulerService()
