import json
import mimetypes
import re
import uuid
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from dashboard.decorators import feature_required
from dashboard.models import FeatureAccess
from dashboard.permissions import has_feature_access, is_super_admin
from dashboard.views import base_context
from tools.bondreminder.app.bond_logic import BondReminder
from tools.bondreminder.app.config import APP_DIR, BOND_CACHE_FILE, UPLOAD_DIR
from tools.bondreminder.app.customer_logic import (
    call_identity_ai,
    check_birthday_jobs,
    fill_identity_to_customer_table,
)
from tools.bondreminder.app.logging_utils import append_log, clear_logs, read_logs
from tools.bondreminder.app.scheduler import scheduler_service
from tools.bondreminder.app.storage import (
    bond_preview,
    cache_bond_table,
    import_customer_table,
    load_config,
    load_contacts,
    load_customer_data,
    load_customer_settings,
    public_config,
    public_customer_settings,
    save_config,
    save_contacts,
    save_customer_data,
    save_customer_settings,
)


ALLOWED_TABLE_EXTENSIONS = {'.xlsx', '.xls', '.csv'}
ALLOWED_IDENTITY_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.pdf'}
STATIC_DIR = APP_DIR / 'static'


def ok(data=None, **kwargs):
    payload = {'ok': True}
    if data is not None:
        payload['data'] = data
    payload.update(kwargs)
    return JsonResponse(payload)


def error(message, status=400):
    append_log(f'请求失败: {message}')
    return JsonResponse({'ok': False, 'error': str(message)}, status=status)


def json_body(request, default):
    if not request.body:
        return default
    try:
        return json.loads(request.body.decode('utf-8'))
    except Exception:
        return default


def require_bond_access(request, action):
    if has_feature_access(request.user, 'bondreminder', action):
        return None
    if request.path.startswith('/tools/bond-reminder/api/'):
        return JsonResponse({'ok': False, 'error': '无权限访问'}, status=403)
    raise PermissionDenied


def require_api_access(action):
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            denied = require_bond_access(request, action)
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
    safe_name = get_valid_filename(uploaded_file.name) or f'upload{ext}'
    filename = f'{uuid.uuid4().hex}_{safe_name}'
    path = UPLOAD_DIR / filename
    with path.open('wb') as target:
        for chunk in uploaded_file.chunks():
            target.write(chunk)
    return path


def preserve_secret_update(current, incoming, key):
    if key not in incoming:
        return
    if incoming.get(key):
        current[key] = incoming[key]
    elif incoming.get(f'clear_{key}'):
        current[key] = ''


def normalize_task(task):
    name = str(task.get('name', '')).strip()
    if not name:
        raise ValueError('任务名称不能为空')
    send_type = task.get('send_type', 'email')
    if send_type not in {'email', 'sms'}:
        raise ValueError('发送方式必须为 email 或 sms')
    receivers = [str(item).strip() for item in task.get('receivers', []) if str(item).strip()]
    if not receivers:
        raise ValueError('请至少添加一个收件人/手机号')
    time_config = task.get('time_config', {}) or {}
    time_type = time_config.get('type', 'once')
    normalized_time = {'type': time_type, 'time': time_config.get('time', '00:00')}
    if time_type == 'once':
        normalized_time['date'] = time_config.get('date')
    elif time_type == 'weekly':
        normalized_time['weekdays'] = time_config.get('weekdays', [])
    elif time_type != 'daily':
        raise ValueError('不支持的发送策略')
    return {
        'name': name,
        'send_type': send_type,
        'subject': task.get('subject') or f'自定义任务：{name}',
        'receivers': receivers,
        'receiver_remarks': task.get('receiver_remarks', []),
        'time_config': normalized_time,
        'content': task.get('content', ''),
        'enabled': bool(task.get('enabled', True)),
        'executed': bool(task.get('executed', False)),
    }


@feature_required('bondreminder')
def index(request):
    context = base_context(request, '高效工具箱')
    context['base_path'] = '/tools/bond-reminder'
    context['can_manage_permissions'] = is_super_admin(request.user)
    return render(request, 'bondreminder/index.html', context)


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
def api_health(request):
    return ok({'status': 'running', 'bond_cache_exists': BOND_CACHE_FILE.exists()})


@require_api_access(FeatureAccess.ACTION_VIEW)
@require_http_methods(['GET', 'POST'])
def api_config(request):
    if request.method == 'GET':
        return ok(public_config())
    denied = require_bond_access(request, FeatureAccess.ACTION_USE)
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
    append_log('债券配置已保存。')
    return ok(public_config(saved))


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_upload_bond_data(request):
    try:
        header = int(request.POST.get('header', request.POST.get('header_row_index', 0)) or 0)
        path = save_upload(request.FILES.get('file'), ALLOWED_TABLE_EXTENSIONS)
        df = cache_bond_table(path, header)
        config = load_config()
        columns = [str(col) for col in df.columns]
        defaults = config.get('default_column_mappings', {})
        if not config.get('date_columns'):
            config['date_columns'] = [col for col in defaults.get('date_columns', []) if col in columns]
        if not config.get('display_columns'):
            config['display_columns'] = [col for col in defaults.get('display_columns', []) if col in columns]
        save_config(config)
        scheduler_service.restart()
        append_log(f'债券数据已上传并缓存: {path.name}')
        return ok(bond_preview())
    except Exception as exc:
        return error(exc)


@require_api_access(FeatureAccess.ACTION_VIEW)
def api_bond_preview(request):
    try:
        return ok(bond_preview())
    except Exception as exc:
        return error(exc)


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_run_weekly(request):
    logs = BondReminder(load_config()).run_weekly_check()
    return ok({'logs': logs})


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_run_daily(request):
    logs = BondReminder(load_config()).run_daily_check()
    return ok({'logs': logs})


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_run_manual(request):
    config = load_config()
    logs = []
    reminder = BondReminder(config)
    if config.get('weekly_enabled', True):
        logs.extend(reminder.run_weekly_check())
    if config.get('daily_enabled', False):
        logs.extend(BondReminder(config).run_daily_check())
    if not logs:
        append_log('当前未启用任何任务，无法执行调试。')
    return ok({'logs': logs})


@require_api_access(FeatureAccess.ACTION_VIEW)
@require_http_methods(['GET', 'POST'])
def api_contacts(request):
    if request.method == 'GET':
        return ok(load_contacts())
    denied = require_bond_access(request, FeatureAccess.ACTION_USE)
    if denied:
        return denied
    contacts = json_body(request, [])
    if not isinstance(contacts, list):
        return error('通讯录必须是数组')
    phone_pattern = re.compile(r'^1[3-9]\d{9}$')
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    for idx, contact in enumerate(contacts, start=1):
        phone = str(contact.get('phone', '')).strip()
        email = str(contact.get('email', '')).strip()
        if phone and not phone_pattern.match(phone):
            return error(f'第 {idx} 行手机号格式不正确')
        if email and not email_pattern.match(email):
            return error(f'第 {idx} 行邮箱格式不正确')
    save_contacts(contacts)
    append_log('通讯录已保存。')
    return ok(load_contacts())


@require_api_access(FeatureAccess.ACTION_VIEW)
@require_http_methods(['GET', 'POST'])
def api_tasks(request):
    if request.method == 'GET':
        return ok(load_config().get('custom_tasks', []))
    denied = require_bond_access(request, FeatureAccess.ACTION_USE)
    if denied:
        return denied
    try:
        task = json_body(request, {})
        config = load_config()
        tasks = config.setdefault('custom_tasks', [])
        tasks.append(normalize_task(task))
        save_config(config)
        scheduler_service.restart()
        append_log(f"自定义任务已新增: {task.get('name', '未命名任务')}")
        return ok(tasks)
    except Exception as exc:
        return error(exc)


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['PUT', 'DELETE'])
def api_task_detail(request, index):
    config = load_config()
    tasks = config.setdefault('custom_tasks', [])
    if index < 0 or index >= len(tasks):
        return error('任务不存在', 404)
    if request.method == 'DELETE':
        removed = tasks.pop(index)
        save_config(config)
        scheduler_service.restart()
        append_log(f"自定义任务已删除: {removed.get('name', '未命名任务')}")
        return ok(tasks)
    try:
        task = json_body(request, {})
        old = tasks[index]
        new_task = normalize_task(task)
        if old.get('executed', False):
            new_task['executed'] = False
            new_task['enabled'] = True
        tasks[index] = new_task
        save_config(config)
        scheduler_service.restart()
        append_log(f"自定义任务已更新: {new_task.get('name', '未命名任务')}")
        return ok(tasks)
    except Exception as exc:
        return error(exc)


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_task_toggle(request, index):
    config = load_config()
    tasks = config.setdefault('custom_tasks', [])
    if index < 0 or index >= len(tasks):
        return error('任务不存在', 404)
    task = tasks[index]
    if task.get('executed', False):
        task['executed'] = False
        task['enabled'] = True
    else:
        task['enabled'] = not task.get('enabled', True)
    save_config(config)
    scheduler_service.restart()
    append_log(f"自定义任务状态已切换: {task.get('name', '未命名任务')}")
    return ok(tasks)


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_task_run(request, index):
    config = load_config()
    tasks = config.setdefault('custom_tasks', [])
    if index < 0 or index >= len(tasks):
        return error('任务不存在', 404)
    reminder = BondReminder(config)
    reminder.run_custom_task(tasks[index])
    return ok({'logs': reminder.logs})


@require_api_access(FeatureAccess.ACTION_VIEW)
@require_http_methods(['GET', 'DELETE'])
def api_logs(request):
    if request.method == 'DELETE':
        denied = require_bond_access(request, FeatureAccess.ACTION_USE)
        if denied:
            return denied
        clear_logs()
        return ok([])
    limit = int(request.GET.get('limit', 2000))
    return ok(read_logs(limit))


@require_api_access(FeatureAccess.ACTION_VIEW)
@require_http_methods(['GET', 'POST'])
def api_customer_data(request):
    if request.method == 'GET':
        return ok(load_customer_data())
    denied = require_bond_access(request, FeatureAccess.ACTION_USE)
    if denied:
        return denied
    data = json_body(request, {})
    columns = data.get('columns', [])
    rows = data.get('rows', [])
    if not isinstance(columns, list) or not isinstance(rows, list):
        return error('客户表数据格式不正确')
    save_customer_data({'columns': columns, 'rows': rows})
    append_log(f'客户表已保存：{len(rows)} 行，{len(columns)} 列。')
    return ok(load_customer_data())


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_upload_customer_data(request):
    try:
        path = save_upload(request.FILES.get('file'), ALLOWED_TABLE_EXTENSIONS)
        data = import_customer_table(path)
        append_log(f"客户表已导入：{path.name}，{len(data.get('rows', []))} 行，{len(data.get('columns', []))} 列。")
        return ok(data)
    except Exception as exc:
        return error(exc)


@require_api_access(FeatureAccess.ACTION_VIEW)
@require_http_methods(['GET', 'POST'])
def api_customer_settings(request):
    if request.method == 'GET':
        return ok(public_customer_settings())
    denied = require_bond_access(request, FeatureAccess.ACTION_USE)
    if denied:
        return denied
    incoming = json_body(request, {})
    current = load_customer_settings()
    api_key = current.get('api_key', '')
    current.update(incoming)
    current['api_key'] = api_key
    preserve_secret_update(current, incoming, 'api_key')
    saved = save_customer_settings(current)
    append_log(
        '客户管理设置已保存：'
        f"生日提醒={'启用' if saved.get('birthday_enabled') else '停用'}，"
        f"发送时间={saved.get('send_time', '')}，"
        f"手机号列={saved.get('phone_column', '') or '-'}，"
        f"生日列={saved.get('birthday_column', '') or '-'}。"
    )
    return ok(public_customer_settings(saved))


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_identity_ocr(request):
    try:
        path = save_upload(request.FILES.get('file'), ALLOWED_IDENTITY_EXTENSIONS)
        append_log(f'开始身份证识别：{path.name}')
        settings = load_customer_settings()
        result = call_identity_ai(path, settings)
        filled = fill_identity_to_customer_table(result)
        append_log(f"身份证识别完成：姓名={filled.get('name') or '-'}，生日={filled.get('birthday') or '-'}。")
        return ok({'raw': result, 'filled': filled})
    except Exception as exc:
        return error(exc)


@require_api_access(FeatureAccess.ACTION_USE)
@require_http_methods(['POST'])
def api_birthday_check(request):
    try:
        result = check_birthday_jobs(force=True)
        append_log(
            '手动生日提醒检查完成：'
            f"客户提醒 {result.get('customer_count', 0)} 条，"
            f"订单提醒 {result.get('merchant_count', 0)} 条，"
            f"是否发送={'是' if result.get('sent') else '否'}。"
        )
        return ok(result)
    except Exception as exc:
        return error(exc)
