"""JSON API endpoints used by the Vue frontend."""

import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import FeatureAccess
from .permissions import ROLE_LABELS, features_for_user, has_feature_access, is_super_admin, role_for_user


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


def serialize_feature(feature):
    return {
        'key': feature.key,
        'name': feature.name,
        'path': FEATURE_PATHS.get(feature.key, '/'),
        'url_name': feature.url_name,
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
    if not has_feature_access(request.user, 'overview', FeatureAccess.ACTION_VIEW):
        return api_error('无权限访问。', status=403)
    return api_ok(OVERVIEW_DATA)


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
