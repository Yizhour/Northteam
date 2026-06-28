from django.shortcuts import render

from .api_views import bond_reminder_overview
from .decorators import feature_required
from .permissions import features_for_user, is_super_admin

NAV_FEATURE_KEYS = {'overview', 'projects', 'tools', 'info', 'files', 'mistakes', 'interns'}


def base_context(request, active_nav):
    """Return shared layout data for every dashboard page."""
    nav_items = [
        {'label': feature.name, 'url_name': feature.url_name}
        for feature in features_for_user(request.user)
        if feature.key in NAV_FEATURE_KEYS and feature.url_name
    ]
    return {
        'nav_items': nav_items,
        'active_nav': active_nav,
        'can_manage_permissions': is_super_admin(request.user),
    }


@feature_required('overview')
def home(request):
    """Render the first dashboard page for the internal OA-style workspace."""
    context = base_context(request, '概况')
    context.update(
        {
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
                'NorthTeam2 内部管理系统首版已初始化。',
                '后续可逐步接入项目、文件、错题本等业务模块。',
            ],
            'bond_reminder': bond_reminder_overview(),
        }
    )
    return render(request, 'dashboard/home.html', context)


@feature_required('tools')
def tools(request):
    """Render the toolbox landing page with integrated internal tools."""
    context = base_context(request, '高效工具箱')
    context['tools'] = [
        {
            'title': '付息兑付提醒',
            'description': '进入债券付息、兑付、每日自查和提醒任务工具。',
            'url_name': 'bond_reminder',
        }
    ]
    return render(request, 'dashboard/tools.html', context)


def placeholder(request, page_title):
    """Render a shared placeholder page for modules that will be built later."""
    context = base_context(request, page_title)
    context['page_title'] = page_title
    return render(request, 'dashboard/placeholder.html', context)


@feature_required('projects')
def projects(request):
    return placeholder(request, '项目空间')


@feature_required('info')
def info(request):
    return placeholder(request, '常用信息')


@feature_required('files')
def files(request):
    return placeholder(request, '文件共享空间')


@feature_required('mistakes')
def mistakes(request):
    return placeholder(request, '错题本')


@feature_required('interns')
def interns(request):
    context = base_context(request, '实习生登记')
    context['intern_share_token'] = ''
    return render(request, 'dashboard/interns.html', context)


def intern_share(request, token):
    context = base_context(request, '实习生工作安排')
    context['intern_share_token'] = token
    context['hide_chrome'] = True
    return render(request, 'dashboard/interns.html', context)
