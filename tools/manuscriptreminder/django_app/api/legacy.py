import json
import mimetypes
import tempfile
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from dashboard.decorators import feature_required
from dashboard.models import FeatureAccess
from dashboard.permissions import has_feature_access, is_super_admin
from dashboard.views import base_context
from tools.manuscriptreminder.app.config import APP_DIR
from tools.manuscriptreminder.app.logging_utils import clear_logs, read_logs
from tools.manuscriptreminder.app.manuscript_logic import ManuscriptReminder
from tools.manuscriptreminder.app.scheduler import run_with_task_lock, scheduler_service
from tools.manuscriptreminder.app.storage import (
    load_config,
    public_config,
    save_config,
    save_table_from_upload,
    table_preview,
)


ALLOWED_TABLE_EXTENSIONS = {'.xlsx', '.xls', '.csv'}
STATIC_DIR = APP_DIR / 'static'


def ok(data=None, **kwargs):
    payload = {'ok': True}
    if data is not None:
        payload['data'] = data
    payload.update(kwargs)
    return JsonResponse(payload)


def error(message, status=400):
    return JsonResponse({'ok': False, 'error': str(message)}, status=status)


def json_body(request, default):
    if not request.body:
        return default
    try:
        return json.loads(request.body.decode('utf-8'))
    except Exception:
        return default


def require_access(request, action):
    if not request.user.is_authenticated:
        if request.path.startswith('/tools/manuscript-reminder/api/'):
            return JsonResponse({'ok': False, 'error': '请先登录。'}, status=401)
        raise PermissionDenied
    if has_feature_access(request.user, 'manuscriptreminder', action):
        return None
    if request.path.startswith('/tools/manuscript-reminder/api/'):
        return JsonResponse({'ok': False, 'error': '无权限访问'}, status=403)
    raise PermissionDenied


def require_api_access(action):
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            denied = require_access(request, action)
            if denied:
                return denied
            return view_func(request, *args, **kwargs)

        return csrf_exempt(wrapped)

    return decorator


def save_upload(uploaded_file, allowed_exts):
    if not uploaded_file or not uploaded_file.name:
        raise ValueError('未上传文件')
    ext = Path(uploaded_file.name).suffix.lower()
    if ext not in allowed_exts:
        raise ValueError(f'不支持的文件类型: {ext}')
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as target:
        for chunk in uploaded_file.chunks():
            target.write(chunk)
        return Path(target.name)


def remove_temp_upload(path):
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def reconcile_columns(config, columns):
    defaults = config.get('default_column_mappings', {})
    for key in ['date_columns', 'display_columns']:
        selected = [col for col in config.get(key, []) if col in columns]
        if not selected:
            selected = [col for col in defaults.get(key, []) if col in columns]
        config[key] = selected
    for key in ['owner_column', 'archive_deadline_column', 'association_deadline_column']:
        if config.get(key) not in columns:
            default = load_config().get(key)
            if default in columns:
                config[key] = default


def preserve_secret_update(current, incoming, key):
    if key not in incoming:
        return
    if incoming.get(key):
        current[key] = incoming[key]
    elif incoming.get(f'clear_{key}'):
        current[key] = ''


@feature_required('manuscriptreminder')
def index(request):
    context = base_context(request, '高效工具箱')
    context['base_path'] = '/tools/manuscript-reminder'
    context['can_manage_permissions'] = is_super_admin(request.user)
    return render(request, 'manuscriptreminder/index.html', context)


@require_api_access(FeatureAccess.ACTION_VIEW)
def static_asset(request, path):
    target = (STATIC_DIR / path).resolve()
    try:
        target.relative_to(STATIC_DIR.resolve())
    except ValueError as exc:
        raise Http404 from exc
    if not target.is_file():
        raise Http404
    content_type, _ = mimetypes.guess_type(target)
    return FileResponse(target.open('rb'), content_type=content_type or 'application/octet-stream')


@require_api_access(FeatureAccess.ACTION_VIEW)
@require_http_methods(['GET', 'POST'])
def api_config(request):
    if request.method == 'GET':
        return ok(public_config())
    denied = require_access(request, FeatureAccess.ACTION_USE)
    if denied:
        return denied
    incoming = json_body(request, {})
    current = load_config()
    auth_code = current.get('auth_code', '')
    current.update(incoming)
    current['auth_code'] = auth_code
    preserve_secret_update(current, incoming, 'auth_code')
    saved = save_config(current)
    scheduler_service.restart()
    return ok(public_config(saved))


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_upload_data(request):
    path = None
    try:
        header = int(request.POST.get('header', request.POST.get('header_row_index', 0)) or 0)
        uploaded_file = request.FILES.get('file')
        source_name = uploaded_file.name if uploaded_file else ''
        path = save_upload(uploaded_file, ALLOWED_TABLE_EXTENSIONS)
        columns, _ = save_table_from_upload(path, header, source_name=source_name)
        config = load_config()
        reconcile_columns(config, columns)
        save_config(config)
        scheduler_service.restart()
        return ok(table_preview())
    except Exception as exc:
        return error(exc)
    finally:
        remove_temp_upload(path)


@require_api_access(FeatureAccess.ACTION_VIEW)
def api_preview(request):
    try:
        return ok(table_preview())
    except Exception as exc:
        return error(exc)


@require_api_access(FeatureAccess.ACTION_VIEW)
def api_overview(request):
    return ok(ManuscriptReminder(load_config()).collect_overview())


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_run_weekly(request):
    logs = run_with_task_lock(lambda: ManuscriptReminder(load_config()).run_weekly_check())
    if logs is None:
        return error('发送任务正在执行，请稍后再试。', status=409)
    return ok({'logs': logs})


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_run_daily(request):
    logs = run_with_task_lock(lambda: ManuscriptReminder(load_config()).run_daily_check())
    if logs is None:
        return error('发送任务正在执行，请稍后再试。', status=409)
    return ok({'logs': logs})


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_run_manual(request):
    def callback():
        config = load_config()
        logs = []
        if config.get('weekly_enabled', True):
            logs.extend(ManuscriptReminder(config).run_weekly_check())
        if config.get('daily_enabled', False):
            logs.extend(ManuscriptReminder(config).run_daily_check())
        return logs

    logs = run_with_task_lock(callback)
    if logs is None:
        return error('发送任务正在执行，请稍后再试。', status=409)
    return ok({'logs': logs})


@require_api_access(FeatureAccess.ACTION_VIEW)
@require_http_methods(['GET', 'DELETE'])
def api_logs(request):
    if request.method == 'DELETE':
        denied = require_access(request, FeatureAccess.ACTION_USE)
        if denied:
            return denied
        clear_logs()
        return ok([])
    limit = int(request.GET.get('limit', 2000))
    return ok(read_logs(limit))
