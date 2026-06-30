from datetime import datetime, time

from django.utils import timezone

WORK_START = time(9, 0)
WORK_END = time(18, 0)
LUNCH_START = time(12, 0)
LUNCH_END = time(13, 30)


def local_datetime_on(date_value, time_value):
    return timezone.make_aware(datetime.combine(date_value, time_value), timezone.get_current_timezone())


def split_ranges_around_lunch(start_time, end_time):
    local_start = timezone.localtime(start_time)
    local_end = timezone.localtime(end_time)
    if local_start.date() != local_end.date():
        return [(start_time, end_time)]

    lunch_start = local_datetime_on(local_start.date(), LUNCH_START)
    lunch_end = local_datetime_on(local_start.date(), LUNCH_END)
    if start_time >= lunch_end or end_time <= lunch_start:
        return [(start_time, end_time)]

    ranges = []
    if start_time < lunch_start:
        ranges.append((start_time, min(end_time, lunch_start)))
    if end_time > lunch_end:
        ranges.append((max(start_time, lunch_end), end_time))
    return [(start, end) for start, end in ranges if start < end]
