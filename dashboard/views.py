from django.shortcuts import render


NAV_ITEMS = [
    {'label': '概况', 'url_name': 'dashboard:home'},
    {'label': '项目空间', 'url_name': 'dashboard:projects'},
    {'label': '高效工具箱', 'url_name': 'dashboard:tools'},
    {'label': '常用信息', 'url_name': 'dashboard:info'},
    {'label': '文件共享空间', 'url_name': 'dashboard:files'},
    {'label': '错题本', 'url_name': 'dashboard:mistakes'},
    {'label': '实习生登记', 'url_name': 'dashboard:interns'},
]


def _base_context(active_nav):
    """Return shared layout data for every dashboard page."""
    return {
        'nav_items': NAV_ITEMS,
        'active_nav': active_nav,
    }


def home(request):
    """Render the first dashboard page for the internal OA-style workspace."""
    context = _base_context('概况')
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
        }
    )
    return render(request, 'dashboard/home.html', context)


def tools(request):
    """Render the toolbox landing page with integrated internal tools."""
    context = _base_context('高效工具箱')
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
    context = _base_context(page_title)
    context['page_title'] = page_title
    return render(request, 'dashboard/placeholder.html', context)
