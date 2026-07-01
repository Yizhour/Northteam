from django.contrib.staticfiles import finders
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import URLValidator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .api_views import bond_reminder_overview
from .decorators import feature_required
from .models import CommonWebsite, CommonWebsiteSetting
from .permissions import features_for_user, is_super_admin
from .services.market_yield_refresh import get_refresh_job, refresh_job_payload, start_market_yield_refresh
from .services.market_yields import market_yield_overview

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
    can_manage_common_websites = is_super_admin(request.user)
    common_website_setting = get_common_website_setting()
    editing_common_websites = can_manage_common_websites and request.GET.get('edit_common_websites') == '1'
    context = base_context(request, '概况')
    context.update(
        {
            'bond_reminder': bond_reminder_overview(),
            'market_yields': market_yield_overview(),
            'market_yield_refresh': refresh_job_payload(get_refresh_job()),
            'common_website_links': CommonWebsite.objects.filter(is_active=True),
            'common_website_admin_items': CommonWebsite.objects.all() if editing_common_websites else [],
            'common_websites_per_row': common_website_setting.cards_per_row,
            'can_manage_common_websites': can_manage_common_websites,
            'editing_common_websites': editing_common_websites,
        }
    )
    return render(request, 'dashboard/home.html', context)


def get_common_website_setting():
    setting, _ = CommonWebsiteSetting.objects.get_or_create(key='default')
    if setting.cards_per_row not in (2, 3, 4, 5):
        setting.cards_per_row = 3
        setting.save(update_fields=['cards_per_row', 'updated_at'])
    return setting


def _redirect_common_website_edit():
    return redirect('/?edit_common_websites=1')


def _require_common_website_admin(request):
    if not is_super_admin(request.user):
        raise PermissionDenied


def _clean_common_website_payload(post_data):
    name = (post_data.get('name') or '').strip()
    url = (post_data.get('url') or '').strip()
    if url and '://' not in url:
        url = f'https://{url}'
    try:
        sort_order = int(post_data.get('sort_order') or 100)
    except (TypeError, ValueError):
        sort_order = 100
    is_active = post_data.get('is_active') == 'on'
    if not name:
        raise ValidationError('网站名不能为空。')
    if not url:
        raise ValidationError('网站链接不能为空。')
    URLValidator()(url)
    return {
        'name': name,
        'url': url,
        'sort_order': max(0, sort_order),
        'is_active': is_active,
    }


@require_POST
@feature_required('overview')
def common_website_create(request):
    _require_common_website_admin(request)
    try:
        CommonWebsite.objects.create(**_clean_common_website_payload(request.POST))
        messages.success(request, '常用网站已添加。')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return _redirect_common_website_edit()


@require_POST
@feature_required('overview')
def common_website_update(request, website_id):
    _require_common_website_admin(request)
    website = get_object_or_404(CommonWebsite, pk=website_id)
    try:
        payload = _clean_common_website_payload(request.POST)
        for field, value in payload.items():
            setattr(website, field, value)
        website.save(update_fields=['name', 'url', 'sort_order', 'is_active', 'updated_at'])
        messages.success(request, '常用网站已更新。')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return _redirect_common_website_edit()


@require_POST
@feature_required('overview')
def common_website_delete(request, website_id):
    _require_common_website_admin(request)
    get_object_or_404(CommonWebsite, pk=website_id).delete()
    messages.success(request, '常用网站已删除。')
    return _redirect_common_website_edit()


@require_POST
@feature_required('overview')
def common_website_layout_update(request):
    _require_common_website_admin(request)
    try:
        cards_per_row = int(request.POST.get('cards_per_row') or 3)
    except (TypeError, ValueError):
        cards_per_row = 3
    if cards_per_row not in (2, 3, 4, 5):
        cards_per_row = 3
    setting = get_common_website_setting()
    setting.cards_per_row = cards_per_row
    setting.save(update_fields=['cards_per_row', 'updated_at'])
    messages.success(request, '常用网站布局已更新。')
    return _redirect_common_website_edit()


@require_POST
@feature_required('overview')
def market_yields_refresh(request):
    job, started = start_market_yield_refresh(request.user)
    overview = market_yield_overview()
    return JsonResponse(
        {
            'ok': True,
            'started': started,
            'refresh': refresh_job_payload(job),
            'market_yields': overview,
            'html': render_market_yields_html(overview, job),
        }
    )


@feature_required('overview')
def market_yields_status(request):
    job = get_refresh_job()
    overview = market_yield_overview()
    return JsonResponse(
        {
            'ok': True,
            'refresh': refresh_job_payload(job),
            'market_yields': overview,
            'html': render_market_yields_html(overview, job),
        }
    )


def render_market_yields_html(overview, job):
    return render_to_string(
        'dashboard/partials/market_yields.html',
        {
            'market_yields': overview,
            'market_yield_refresh': refresh_job_payload(job),
        },
    )


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


def interns_script(request):
    script_path = finders.find('dashboard/js/interns.js')
    if not script_path:
        raise Http404('Intern schedule script not found.')
    with open(script_path, 'rb') as script_file:
        return HttpResponse(script_file.read(), content_type='application/javascript; charset=utf-8')
