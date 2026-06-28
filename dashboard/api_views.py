"""JSON API endpoints used by the Vue frontend."""

import json
from datetime import datetime, time, timedelta

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from tools.bondreminder.app.bond_logic import BondReminder
from tools.bondreminder.app.storage import load_config

from .models import FeatureAccess, Intern, InternSchedule
from .permissions import (
    ROLE_LABELS,
    features_for_user,
    has_feature_access,
    is_super_admin,
    role_for_user,
)


FEATURE_PATHS = {
    'overview': '/',
    'projects': '/projects',
    'tools': '/tools',
    'bondreminder': '/tools/bond-reminder/',
    'info': '/info',
    'files': '/files',
    'mistakes': '/mistakes',
    'interns': '/interns',
}

OVERVIEW_DATA = {
    'summary_cards': [
        {'label': '进行中项目', 'value': '12', 'hint': '本周新增 2 项'},
        {'label': '待处理事项', 'value': '8', 'hint': '含 3 项今日到期'},
        {'label': '共享文件', 'value': '36', 'hint': '最近更新 5 份'},
        {'label': '实习生登记', 'value': '4', 'hint': '待复核资料 1 份'},
    ],
    'quick_links': [
        {'label': '新建项目台账', 'description': '预留项目空间入口'},
        {'label': '上传共享文件', 'description': '预留文件共享入口'},
        {'label': '登记实习生', 'description': '预留人员登记入口'},
        {'label': '查看常用信息', 'description': '预留信息查询入口'},
    ],
    'todos': [
        '复核本周项目材料归档状态',
        '整理常用模板与制度文件',
        '确认实习生登记信息完整性',
    ],
    'announcements': [
        'NorthTeam2 内部管理系统已切换为 Vue 前端。',
        '后端继续提供权限、Admin 和业务 API。',
    ],
}


def api_ok(data=None, **kwargs):
    payload = {'ok': True}
    if data is not None:
        payload['data'] = data
    payload.update(kwargs)
    return JsonResponse(payload)


def api_error(message, status=400):
    return JsonResponse({'ok': False, 'error': message}, status=status)


def parse_json(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def validation_message(exc):
    if hasattr(exc, 'message_dict'):
        messages = []
        for field_messages in exc.message_dict.values():
            messages.extend(field_messages)
        return messages[0] if messages else '数据校验失败。'
    if hasattr(exc, 'messages') and exc.messages:
        return exc.messages[0]
    return str(exc)


def display_user_name(user):
    full_name = user.get_full_name().strip()
    return full_name or user.first_name.strip() or user.get_username()


def user_role_flags(user):
    role = role_for_user(user)
    return {
        'role': role,
        'is_intern': role == FeatureAccess.ROLE_INTERN,
        'is_member': role == FeatureAccess.ROLE_MEMBER,
        'can_manage_all': role in {FeatureAccess.ROLE_SUPER_ADMIN, FeatureAccess.ROLE_TEAM_LEAD},
        'can_view_all': role in {
            FeatureAccess.ROLE_SUPER_ADMIN,
            FeatureAccess.ROLE_TEAM_LEAD,
            FeatureAccess.ROLE_MEMBER,
        },
    }


def parse_schedule_datetime(value):
    parsed = parse_datetime(str(value or ''))
    if parsed is None:
        raise ValueError('时间格式不正确。')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def parse_week_start(value):
    parsed = parse_date(str(value or '')) if value else timezone.localdate()
    if parsed is None:
        parsed = timezone.localdate()
    return parsed - timedelta(days=parsed.weekday())


def intern_queryset():
    return Intern.objects.filter(is_active=True).order_by('name', 'id')


def get_visible_intern_or_error(user, intern_id):
    flags = user_role_flags(user)
    if not flags['can_view_all']:
        return None, api_error('无权限访问。', status=403)
    try:
        return intern_queryset().get(id=intern_id), None
    except (Intern.DoesNotExist, TypeError, ValueError):
        return None, api_error('实习生不存在。', status=404)


def get_intern_by_token(token):
    try:
        return Intern.objects.get(access_token=token, is_active=True)
    except Intern.DoesNotExist:
        return None


def can_edit_schedule(user, schedule, public_intern=None):
    if public_intern is not None:
        return False
    flags = user_role_flags(user)
    if flags['can_manage_all']:
        return True
    can_use = has_feature_access(user, 'interns', FeatureAccess.ACTION_USE)
    if can_use and schedule.schedule_type == InternSchedule.TYPE_LEAVE:
        return True
    if flags['is_member'] and schedule.schedule_type == InternSchedule.TYPE_WORK:
        return schedule.created_by_id == user.id
    return False


def serialize_intern(intern, request=None):
    share_url = f'/interns/share/{intern.access_token}/'
    if request is not None:
        share_url = request.build_absolute_uri(share_url)
    return {
        'id': intern.id,
        'name': intern.name,
        'note': intern.note,
        'share_url': share_url,
        'is_active': intern.is_active,
    }


def serialize_schedule(schedule, user=None, public_intern=None):
    return {
        'id': schedule.id,
        'intern_id': schedule.intern_id,
        'intern_name': schedule.intern.name,
        'created_by_id': schedule.created_by_id,
        'created_by_name': display_user_name(schedule.created_by) if schedule.created_by else '实习生本人',
        'schedule_type': schedule.schedule_type,
        'schedule_type_label': schedule.get_schedule_type_display(),
        'title': schedule.title,
        'notes': schedule.notes,
        'start_time': timezone.localtime(schedule.start_time).isoformat(),
        'end_time': timezone.localtime(schedule.end_time).isoformat(),
        'can_edit': can_edit_schedule(user, schedule, public_intern),
        'can_delete': can_edit_schedule(user, schedule, public_intern),
    }


def serialize_feature(feature):
    return {
        'key': feature.key,
        'name': feature.name,
        'path': FEATURE_PATHS.get(feature.key, '/'),
        'url_name': feature.url_name,
    }


def bond_reminder_overview():
    reminder = BondReminder(load_config())
    start_date, end_date = reminder.get_week_range()
    today = datetime.now().date()
    weekly = reminder.collect_events(start_date, end_date)
    today_events = [
        event
        for event in weekly['events']
        if event['date_str'] == str(today)
    ]
    return {
        'available': True,
        'configured': weekly['configured'],
        'week_range': {
            'start': str(start_date),
            'end': str(end_date),
            'label': f'{start_date.strftime("%m.%d")} - {end_date.strftime("%m.%d")}',
        },
        'today': str(today),
        'display_columns': weekly['display_columns'],
        'weekly_events': weekly['events'],
        'today_events': today_events,
        'weekly_count': len(weekly['events']),
        'today_count': len(today_events),
    }


@ensure_csrf_cookie
def session_info(request):
    role = role_for_user(request.user)
    features = [
        serialize_feature(feature)
        for feature in features_for_user(request.user)
        if feature.key in FEATURE_PATHS and feature.key != 'bondreminder'
    ]
    return api_ok(
        {
            'authenticated': request.user.is_authenticated,
            'username': request.user.get_username() if request.user.is_authenticated else '',
            'role': role,
            'role_label': ROLE_LABELS.get(role, role),
            'is_staff': request.user.is_staff if request.user.is_authenticated else False,
            'can_manage_permissions': is_super_admin(request.user),
            'features': features,
            'csrf_token': get_token(request),
        }
    )


def intern_schedule_capabilities(user=None, intern=None, public=False):
    if public:
        return {
            'can_view_all': False,
            'can_manage_interns': False,
            'can_create_work': False,
            'can_request_leave': False,
            'can_manage_all': False,
        }
    flags = user_role_flags(user)
    can_use = has_feature_access(user, 'interns', FeatureAccess.ACTION_USE)
    return {
        'can_view_all': flags['can_view_all'],
        'can_manage_interns': can_use,
        'can_create_work': can_use,
        'can_request_leave': False,
        'can_manage_all': flags['can_manage_all'],
    }


def intern_schedules_base_check(request):
    if not request.user.is_authenticated:
        return api_error('请先登录。', status=401)
    if not has_feature_access(request.user, 'interns', FeatureAccess.ACTION_VIEW):
        return api_error('无权限访问。', status=403)
    return None


@require_http_methods(['POST'])
def login_api(request):
    payload = parse_json(request)
    user = authenticate(
        request,
        username=str(payload.get('username', '')).strip(),
        password=payload.get('password', ''),
    )
    if user is None:
        return api_error('用户名或密码不正确。', status=400)
    login(request, user)
    return session_info(request)


@require_http_methods(['POST'])
def logout_api(request):
    logout(request)
    return session_info(request)


def overview_api(request):
    data = {
        **OVERVIEW_DATA,
        'bond_reminder': bond_reminder_overview(),
    }
    return api_ok(data)


def tools_api(request):
    if not has_feature_access(request.user, 'tools', FeatureAccess.ACTION_VIEW):
        return api_error('无权限访问。', status=403)
    tools = []
    if has_feature_access(request.user, 'bondreminder', FeatureAccess.ACTION_VIEW):
        tools.append(
            {
                'key': 'bondreminder',
                'title': '付息兑付提醒',
                'description': '进入债券付息、兑付、每日自查和提醒任务工具。',
                'path': '/tools/bond-reminder/',
                'external': True,
                'can_use': has_feature_access(request.user, 'bondreminder', FeatureAccess.ACTION_USE),
            }
        )
    return api_ok({'tools': tools})


@require_http_methods(['GET', 'POST'])
def interns_api(request):
    denied = intern_schedules_base_check(request)
    if denied:
        return denied
    if request.method == 'POST':
        if not has_feature_access(request.user, 'interns', FeatureAccess.ACTION_USE):
            return api_error('无权限维护实习生列表。', status=403)
        payload = parse_json(request)
        name = str(payload.get('name') or '').strip()
        if not name:
            return api_error('实习生姓名不能为空。', status=400)
        intern = Intern.objects.create(
            name=name,
            note=str(payload.get('note') or '').strip(),
            is_active=bool(payload.get('is_active', True)),
        )
        return api_ok(serialize_intern(intern, request))

    interns = list(intern_queryset())
    return api_ok(
        {
            'interns': [serialize_intern(intern, request) for intern in interns],
            'current_user_id': request.user.id,
            'capabilities': intern_schedule_capabilities(request.user),
        }
    )


@require_http_methods(['PATCH', 'DELETE'])
def intern_detail_api(request, intern_id):
    denied = intern_schedules_base_check(request)
    if denied:
        return denied
    if not has_feature_access(request.user, 'interns', FeatureAccess.ACTION_USE):
        return api_error('无权限维护实习生列表。', status=403)
    try:
        intern = Intern.objects.get(id=intern_id)
    except Intern.DoesNotExist:
        return api_error('实习生不存在。', status=404)

    if request.method == 'DELETE':
        intern.is_active = False
        intern.save(update_fields=['is_active', 'updated_at'])
        return api_ok({'deleted': True})

    payload = parse_json(request)
    if 'name' in payload:
        intern.name = str(payload.get('name') or '').strip()
    if 'note' in payload:
        intern.note = str(payload.get('note') or '').strip()
    if 'is_active' in payload:
        intern.is_active = bool(payload.get('is_active'))
    if not intern.name:
        return api_error('实习生姓名不能为空。', status=400)
    intern.save()
    return api_ok(serialize_intern(intern, request))


@require_http_methods(['GET', 'POST'])
def intern_schedules_api(request):
    denied = intern_schedules_base_check(request)
    if denied:
        return denied

    if request.method == 'GET':
        intern_id = request.GET.get('intern_id') or request.user.id
        intern, error_response = get_visible_intern_or_error(request.user, intern_id)
        if error_response:
            return error_response
        week_start = parse_week_start(request.GET.get('week_start'))
        range_start = timezone.make_aware(datetime.combine(week_start, time.min))
        range_end = range_start + timedelta(days=7)
        schedules = (
            InternSchedule.objects.select_related('intern', 'created_by')
            .filter(intern=intern, start_time__lt=range_end, end_time__gt=range_start)
            .order_by('start_time', 'id')
        )
        return api_ok(
            {
                'intern': serialize_intern(intern, request),
                'week_start': str(week_start),
                'week_end': str(week_start + timedelta(days=6)),
                'hours': list(range(9, 18)),
                'schedules': [serialize_schedule(schedule, request.user) for schedule in schedules],
                'capabilities': intern_schedule_capabilities(request.user, intern),
            }
        )

    payload = parse_json(request)
    flags = user_role_flags(request.user)
    can_use = has_feature_access(request.user, 'interns', FeatureAccess.ACTION_USE)
    schedule_type = payload.get('schedule_type') or InternSchedule.TYPE_WORK
    intern_id = payload.get('intern_id')
    intern, error_response = get_visible_intern_or_error(request.user, intern_id)
    if error_response:
        return error_response

    if schedule_type == InternSchedule.TYPE_LEAVE:
        if not can_use:
            return api_error('无权限提交该请假。', status=403)
    elif schedule_type == InternSchedule.TYPE_WORK:
        if not can_use:
            return api_error('无权限新增工作安排。', status=403)
    else:
        return api_error('安排类型不正确。', status=400)

    try:
        schedule = InternSchedule.objects.create(
            intern=intern,
            created_by=request.user,
            schedule_type=schedule_type,
            title=str(payload.get('title') or ('请假' if schedule_type == InternSchedule.TYPE_LEAVE else '')).strip(),
            notes=str(payload.get('notes') or '').strip(),
            start_time=parse_schedule_datetime(payload.get('start_time')),
            end_time=parse_schedule_datetime(payload.get('end_time')),
        )
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except ValidationError as exc:
        return api_error(validation_message(exc), status=400)

    return api_ok(serialize_schedule(schedule, request.user))


@require_http_methods(['GET', 'PATCH', 'DELETE'])
def intern_schedule_detail_api(request, schedule_id):
    denied = intern_schedules_base_check(request)
    if denied:
        return denied
    try:
        schedule = InternSchedule.objects.select_related('intern', 'created_by').get(id=schedule_id)
    except InternSchedule.DoesNotExist:
        return api_error('安排不存在。', status=404)

    _, error_response = get_visible_intern_or_error(request.user, schedule.intern_id)
    if error_response:
        return error_response

    if request.method == 'GET':
        return api_ok(serialize_schedule(schedule, request.user))

    if not can_edit_schedule(request.user, schedule):
        return api_error('无权限修改该安排。', status=403)

    if request.method == 'DELETE':
        schedule.delete()
        return api_ok({'deleted': True})

    payload = parse_json(request)
    flags = user_role_flags(request.user)
    if 'intern_id' in payload:
        if not flags['can_manage_all']:
            return api_error('无权限变更实习生。', status=403)
        intern, error_response = get_visible_intern_or_error(request.user, payload.get('intern_id'))
        if error_response:
            return error_response
        schedule.intern = intern
    if 'schedule_type' in payload:
        next_type = payload.get('schedule_type')
        if not flags['can_manage_all'] and next_type != schedule.schedule_type:
            return api_error('无权限变更安排类型。', status=403)
        schedule.schedule_type = next_type
    if 'title' in payload:
        schedule.title = str(payload.get('title') or '').strip()
    if 'notes' in payload:
        schedule.notes = str(payload.get('notes') or '').strip()
    try:
        if 'start_time' in payload:
            schedule.start_time = parse_schedule_datetime(payload.get('start_time'))
        if 'end_time' in payload:
            schedule.end_time = parse_schedule_datetime(payload.get('end_time'))
        schedule.save()
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except ValidationError as exc:
        return api_error(validation_message(exc), status=400)

    return api_ok(serialize_schedule(schedule, request.user))


@require_http_methods(['GET'])
def intern_public_schedules_api(request, token):
    intern = get_intern_by_token(token)
    if intern is None:
        return api_error('专属链接无效。', status=404)

    week_start = parse_week_start(request.GET.get('week_start'))
    range_start = timezone.make_aware(datetime.combine(week_start, time.min))
    range_end = range_start + timedelta(days=7)
    schedules = (
        InternSchedule.objects.select_related('intern', 'created_by')
        .filter(intern=intern, start_time__lt=range_end, end_time__gt=range_start)
        .order_by('start_time', 'id')
    )
    return api_ok(
        {
            'intern': serialize_intern(intern, request),
            'week_start': str(week_start),
            'week_end': str(week_start + timedelta(days=6)),
            'hours': list(range(9, 18)),
            'schedules': [
                serialize_schedule(schedule, public_intern=intern)
                for schedule in schedules
            ],
            'capabilities': intern_schedule_capabilities(public=True),
        }
    )


@require_http_methods(['GET'])
def intern_public_schedule_detail_api(request, token, schedule_id):
    intern = get_intern_by_token(token)
    if intern is None:
        return api_error('专属链接无效。', status=404)
    try:
        schedule = InternSchedule.objects.select_related('intern', 'created_by').get(id=schedule_id, intern=intern)
    except InternSchedule.DoesNotExist:
        return api_error('安排不存在。', status=404)

    if request.method == 'GET':
        return api_ok(serialize_schedule(schedule, public_intern=intern))


def page_api(request, feature_key):
    if not has_feature_access(request.user, feature_key, FeatureAccess.ACTION_VIEW):
        return api_error('无权限访问。', status=403)
    names = {
        'projects': '项目空间',
        'info': '常用信息',
        'files': '文件共享空间',
        'mistakes': '错题本',
        'interns': '实习生登记',
    }
    return api_ok(
        {
            'title': names.get(feature_key, '功能页面'),
            'message': '该模块已接入前后端分离架构，业务功能将在后续迭代中逐步完善。',
        }
    )
