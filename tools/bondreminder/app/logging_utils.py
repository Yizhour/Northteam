from datetime import datetime
_MAX_LOG_ROWS = 2000


def _log_model():
    try:
        from django.apps import apps
        from django.conf import settings

        if not settings.configured or not apps.ready:
            return None
        return apps.get_model("bondreminder", "BondReminderLog")
    except Exception:
        return None


def append_log(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    model = _log_model()
    if model is None:
        return line
    try:
        model.objects.create(line=line)
        overflow = model.objects.count() - _MAX_LOG_ROWS
        if overflow > 0:
            stale_ids = list(model.objects.order_by("id").values_list("id", flat=True)[:overflow])
            if stale_ids:
                model.objects.filter(id__in=stale_ids).delete()
    except Exception:
        pass
    return line


def read_logs(limit=2000):
    model = _log_model()
    if model is None:
        return []
    try:
        query = model.objects.order_by("id")
        if limit > 0:
            ids = list(query.values_list("id", flat=True).order_by("-id")[:limit])
            if not ids:
                return []
            query = model.objects.filter(id__in=ids).order_by("id")
        return list(query.values_list("line", flat=True))
    except Exception:
        return []


def clear_logs():
    model = _log_model()
    if model is not None:
        try:
            model.objects.all().delete()
        except Exception:
            pass
