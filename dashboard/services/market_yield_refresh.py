import threading
from datetime import timedelta

from django.db import close_old_connections, transaction
from django.utils import timezone

from dashboard.models import MarketYieldRefreshJob
from dashboard.services.market_yields import fetch_recent_market_yields


REFRESH_JOB_KEY = 'default'
RUNNING_TIMEOUT_MINUTES = 20


def _running_is_fresh(job, now):
    if job.status != MarketYieldRefreshJob.STATUS_RUNNING or not job.started_at:
        return False
    return job.started_at >= now - timedelta(minutes=RUNNING_TIMEOUT_MINUTES)


def get_refresh_job():
    job, _ = MarketYieldRefreshJob.objects.get_or_create(key=REFRESH_JOB_KEY)
    now = timezone.now()
    if job.status == MarketYieldRefreshJob.STATUS_RUNNING and not _running_is_fresh(job, now):
        job.status = MarketYieldRefreshJob.STATUS_FAILED
        job.message = '收益率数据更新超时，请重新点击更新。'
        job.finished_at = now
        job.save(update_fields=['status', 'message', 'finished_at', 'updated_at'])
    return job


def refresh_job_payload(job=None):
    job = job or get_refresh_job()
    return {
        'status': job.status,
        'running': job.status == MarketYieldRefreshJob.STATUS_RUNNING,
        'message': job.message,
        'started_at': timezone.localtime(job.started_at).isoformat() if job.started_at else None,
        'finished_at': timezone.localtime(job.finished_at).isoformat() if job.finished_at else None,
        'updated_at': timezone.localtime(job.updated_at).isoformat() if job.updated_at else None,
        'requested_by': job.requested_by,
        'trigger': job.trigger,
    }


def _claim_refresh_job(requested_by='', trigger='manual'):
    now = timezone.now()
    with transaction.atomic():
        job, _ = MarketYieldRefreshJob.objects.select_for_update().get_or_create(key=REFRESH_JOB_KEY)
        if _running_is_fresh(job, now):
            return job, False
        job.status = MarketYieldRefreshJob.STATUS_RUNNING
        job.message = '收益率数据正在更新...'
        job.started_at = now
        job.finished_at = None
        job.requested_by = requested_by
        job.trigger = trigger
        job.save(
            update_fields=[
                'status',
                'message',
                'started_at',
                'finished_at',
                'requested_by',
                'trigger',
                'updated_at',
            ]
        )
    return job, True


def start_market_yield_refresh(user=None, trigger='manual'):
    requested_by = ''
    if user is not None and getattr(user, 'is_authenticated', False):
        requested_by = user.get_username()

    job, acquired = _claim_refresh_job(requested_by=requested_by, trigger=trigger)
    if not acquired:
        return job, False

    thread = threading.Thread(target=_run_refresh_job, name='market-yield-refresh', daemon=True)
    thread.start()
    return job, True


def run_market_yield_refresh(trigger='auto', requested_by='scheduler'):
    job, acquired = _claim_refresh_job(requested_by=requested_by, trigger=trigger)
    if not acquired:
        return {'ok': False, 'message': job.message, 'running': True}
    return _run_refresh_job()


def _run_refresh_job():
    close_old_connections()
    try:
        result = fetch_recent_market_yields()
        now = timezone.now()
        job = MarketYieldRefreshJob.objects.get(key=REFRESH_JOB_KEY)
        if result.get('ok'):
            dates = result.get('dates') or []
            date_text = '、'.join(dates)
            job.status = MarketYieldRefreshJob.STATUS_SUCCESS
            job.message = f'收益率数据已更新：{date_text}' if date_text else '收益率数据已更新。'
        else:
            job.status = MarketYieldRefreshJob.STATUS_FAILED
            job.message = result.get('message') or '收益率数据更新失败。'
        job.finished_at = now
        job.save(update_fields=['status', 'message', 'finished_at', 'updated_at'])
        return result
    except Exception as exc:
        MarketYieldRefreshJob.objects.update_or_create(
            key=REFRESH_JOB_KEY,
            defaults={
                'status': MarketYieldRefreshJob.STATUS_FAILED,
                'message': f'收益率数据更新失败：{exc}',
                'finished_at': timezone.now(),
            },
        )
        return {'ok': False, 'message': f'收益率数据更新失败：{exc}', 'saved': 0, 'dates': []}
    finally:
        close_old_connections()
