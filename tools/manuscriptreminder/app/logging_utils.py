from datetime import datetime

from django.apps import apps
from django.db import DatabaseError


def _log_model():
    try:
        return apps.get_model("manuscriptreminder", "ManuscriptReminderLog")
    except LookupError:
        return None


def append_log(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    model = _log_model()
    if model is not None:
        try:
            model.objects.create(line=line)
        except DatabaseError:
            pass
    return line


def read_logs(limit=2000):
    model = _log_model()
    if model is None:
        return []
    try:
        query = model.objects.order_by("-id")[: int(limit or 2000)]
        return [item.line for item in reversed(list(query))]
    except DatabaseError:
        return []


def clear_logs():
    model = _log_model()
    if model is None:
        return
    try:
        model.objects.all().delete()
    except DatabaseError:
        pass
