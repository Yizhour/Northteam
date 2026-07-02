from django.contrib.staticfiles import finders
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Max, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from .api_views import bond_reminder_overview, manuscript_reminder_overview
from .decorators import feature_required
from .models import CommonWebsite, CommonWebsiteSetting, InfoCard, InfoCardItem, InfoCardPermission, InfoCardSetting
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
            'manuscript_reminder': manuscript_reminder_overview(),
            'market_yields': market_yield_overview(),
            'market_yield_refresh': refresh_job_payload(get_refresh_job()),
            'market_yields_public_url': request.build_absolute_uri(reverse('dashboard:market_yields_public')),
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


def get_info_card_setting():
    setting, _ = InfoCardSetting.objects.get_or_create(key='default')
    if setting.cards_per_row not in (3, 4, 5):
        setting.cards_per_row = 3
        setting.save(update_fields=['cards_per_row', 'updated_at'])
    return setting


def _redirect_common_website_edit():
    return redirect('/?edit_common_websites=1')


def _require_common_website_admin(request):
    if not is_super_admin(request.user):
        raise PermissionDenied


def _require_info_card_admin(request):
    if not is_super_admin(request.user):
        raise PermissionDenied


def _clean_common_website_values(name, url, sort_order, is_active):
    name = (name or '').strip()
    url = (url or '').strip()
    if url and '://' not in url:
        url = f'https://{url}'
    try:
        sort_order = int(sort_order or 100)
    except (TypeError, ValueError):
        sort_order = 100
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


def _clean_common_website_payload(post_data):
    return _clean_common_website_values(
        post_data.get('name'),
        post_data.get('url'),
        post_data.get('sort_order'),
        post_data.get('is_active') == 'on',
    )


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
def common_website_bulk_update(request):
    _require_common_website_admin(request)
    try:
        cards_per_row = int(request.POST.get('cards_per_row') or 3)
    except (TypeError, ValueError):
        cards_per_row = 3
    if cards_per_row not in (2, 3, 4, 5):
        cards_per_row = 3

    errors = []
    updates = []
    deletes = []
    creates = []

    for raw_id in request.POST.getlist('website_id'):
        try:
            website_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if request.POST.get(f'delete_{website_id}') == 'on':
            deletes.append(website_id)
            continue
        try:
            payload = _clean_common_website_values(
                request.POST.get(f'name_{website_id}'),
                request.POST.get(f'url_{website_id}'),
                request.POST.get(f'sort_order_{website_id}'),
                request.POST.get(f'is_active_{website_id}') == 'on',
            )
            updates.append((website_id, payload))
        except ValidationError as exc:
            errors.extend(exc.messages)

    new_name = (request.POST.get('new_name') or '').strip()
    new_url = (request.POST.get('new_url') or '').strip()
    if new_name or new_url:
        try:
            creates.append(
                _clean_common_website_values(
                    new_name,
                    new_url,
                    request.POST.get('new_sort_order'),
                    request.POST.get('new_is_active') == 'on',
                )
            )
        except ValidationError as exc:
            errors.extend(exc.messages)

    if errors:
        messages.error(request, '; '.join(errors))
        return _redirect_common_website_edit()

    with transaction.atomic():
        setting = get_common_website_setting()
        setting.cards_per_row = cards_per_row
        setting.save(update_fields=['cards_per_row', 'updated_at'])

        if deletes:
            CommonWebsite.objects.filter(pk__in=deletes).delete()
        for website_id, payload in updates:
            CommonWebsite.objects.filter(pk=website_id).update(**payload)
        for payload in creates:
            CommonWebsite.objects.create(**payload)

    messages.success(request, '常用网站已统一保存。')
    return _redirect_common_website_edit()


def _redirect_info_cards():
    return redirect('dashboard:info')


def _visible_info_cards_for(user):
    cards = InfoCard.objects.prefetch_related('items', 'permissions__user')
    if is_super_admin(user):
        return cards
    return cards.filter(
        Q(is_restricted=False) | Q(permissions__user=user),
        is_active=True,
    ).distinct()


def _colon_index(line):
    positions = [position for position in (line.find('：'), line.find(':')) if position >= 0]
    return min(positions) if positions else -1


def _parse_info_bulk_content(content, title):
    parsed_title = ''
    items = []
    invalid_lines = []
    for raw_line in (content or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue
        colon_index = _colon_index(line)
        if colon_index < 0:
            if not title and not parsed_title:
                parsed_title = line
            else:
                invalid_lines.append(line)
            continue
        key = line[:colon_index].strip()
        value = line[colon_index + 1 :].strip()
        if key and value:
            items.append((key, value))
        else:
            invalid_lines.append(line)
    return parsed_title, items, invalid_lines


def _clean_info_card_payload(post_data, current_sort_order=None):
    title = (post_data.get('title') or '').strip()
    bulk_content = post_data.get('bulk_content') or ''
    parsed_title, bulk_items, invalid_lines = _parse_info_bulk_content(bulk_content, title)
    if not title and parsed_title:
        title = parsed_title

    manual_items = []
    item_keys = post_data.getlist('item_key')
    item_values = post_data.getlist('item_value')
    for index in range(max(len(item_keys), len(item_values))):
        key = (item_keys[index] if index < len(item_keys) else '').strip()
        value = (item_values[index] if index < len(item_values) else '').strip()
        if not key and not value:
            continue
        if not key or not value:
            invalid_lines.append(f'{key}：{value}'.strip('：'))
            continue
        manual_items.append((key, value))

    items = manual_items or bulk_items
    errors = []
    if not title:
        errors.append('标题不能为空。')
    if invalid_lines:
        errors.append('以下行无法解析为完整键值对：' + '；'.join(invalid_lines))
    if not items:
        errors.append('至少需要添加一条具体信息。')
    if errors:
        raise ValidationError(errors)

    try:
        sort_order = int(post_data.get('sort_order') or current_sort_order or 100)
    except (TypeError, ValueError):
        sort_order = current_sort_order or 100

    allowed_user_ids = []
    for raw_id in post_data.getlist('allowed_user'):
        try:
            allowed_user_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    return {
        'title': title,
        'sort_order': max(0, sort_order),
        'is_active': post_data.get('is_active') == 'on',
        'is_restricted': bool(allowed_user_ids),
        'items': items,
        'allowed_user_ids': allowed_user_ids,
    }


def _next_info_card_sort_order():
    latest = InfoCard.objects.aggregate(value=Max('sort_order'))['value']
    return (latest or 0) + 10


def _save_info_card(card, payload):
    with transaction.atomic():
        card.title = payload['title']
        card.sort_order = payload['sort_order']
        card.is_active = payload['is_active']
        card.is_restricted = payload['is_restricted']
        if card.pk:
            card.save(update_fields=['title', 'sort_order', 'is_active', 'is_restricted', 'updated_at'])
        else:
            card.save()

        card.items.all().delete()
        InfoCardItem.objects.bulk_create(
            [
                InfoCardItem(card=card, key=key, value=value, sort_order=(index + 1) * 10)
                for index, (key, value) in enumerate(payload['items'])
            ]
        )

        card.permissions.all().delete()
        if card.is_restricted and payload['allowed_user_ids']:
            users = User.objects.filter(id__in=payload['allowed_user_ids'], is_active=True)
            InfoCardPermission.objects.bulk_create(
                [InfoCardPermission(card=card, user=user) for user in users],
                ignore_conflicts=True,
            )


def _user_display_name(user):
    full_name = user.get_full_name().strip()
    return full_name or user.first_name.strip() or user.get_username()


@feature_required('info')
def info(request):
    can_manage_info_cards = is_super_admin(request.user)
    setting = get_info_card_setting()
    cards = list(_visible_info_cards_for(request.user))
    for card in cards:
        permissions = list(card.permissions.all())
        card.allowed_user_ids = {permission.user_id for permission in permissions}
        card.visibility_label = '仅 ' + '、'.join(_user_display_name(permission.user) for permission in permissions) + ' 可见'
        card.copy_text = '\n'.join(f'{item.key}：{item.value}' for item in card.items.all())
        card.content_search_text = ' '.join(
            [item.key for item in card.items.all()] + [item.value for item in card.items.all()]
        )

    context = base_context(request, '常用信息')
    context.update(
        {
            'info_cards': cards,
            'info_cards_per_row': setting.cards_per_row,
            'can_manage_info_cards': can_manage_info_cards,
            'active_users': User.objects.filter(is_active=True).order_by('first_name', 'username', 'id')
            if can_manage_info_cards
            else [],
            'next_info_sort_order': _next_info_card_sort_order() if can_manage_info_cards else 100,
        }
    )
    return render(request, 'dashboard/info.html', context)


@require_POST
@feature_required('info')
def info_card_create(request):
    _require_info_card_admin(request)
    try:
        payload = _clean_info_card_payload(request.POST, current_sort_order=_next_info_card_sort_order())
        card = InfoCard()
        _save_info_card(card, payload)
        messages.success(request, '常用信息卡片已添加。')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return _redirect_info_cards()


@require_POST
@feature_required('info')
def info_card_update(request, card_id):
    _require_info_card_admin(request)
    card = get_object_or_404(InfoCard, pk=card_id)
    try:
        payload = _clean_info_card_payload(request.POST, current_sort_order=card.sort_order)
        _save_info_card(card, payload)
        messages.success(request, '常用信息卡片已更新。')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return _redirect_info_cards()


@require_POST
@feature_required('info')
def info_card_delete(request, card_id):
    _require_info_card_admin(request)
    get_object_or_404(InfoCard, pk=card_id).delete()
    messages.success(request, '常用信息卡片已删除。')
    return _redirect_info_cards()


@require_POST
@feature_required('info')
def info_card_order_update(request):
    _require_info_card_admin(request)
    with transaction.atomic():
        for index, raw_id in enumerate(request.POST.getlist('card_id')):
            try:
                card_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            InfoCard.objects.filter(pk=card_id).update(sort_order=(index + 1) * 10)
    messages.success(request, '常用信息排序已更新。')
    return _redirect_info_cards()


@require_POST
@feature_required('info')
def info_card_layout_update(request):
    _require_info_card_admin(request)
    try:
        cards_per_row = int(request.POST.get('cards_per_row') or 3)
    except (TypeError, ValueError):
        cards_per_row = 3
    if cards_per_row not in (3, 4, 5):
        cards_per_row = 3
    setting = get_info_card_setting()
    setting.cards_per_row = cards_per_row
    setting.save(update_fields=['cards_per_row', 'updated_at'])
    messages.success(request, '常用信息布局已更新。')
    return _redirect_info_cards()


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


def market_yields_public(request):
    job = get_refresh_job()
    return render(
        request,
        'dashboard/market_yields_public.html',
        {
            'hide_chrome': True,
            'market_yields': market_yield_overview(),
            'market_yield_refresh': refresh_job_payload(job),
        },
    )


def market_yields_public_status(request):
    job = get_refresh_job()
    overview = market_yield_overview()
    return JsonResponse(
        {
            'ok': True,
            'market_yields': overview,
            'html': render_market_yields_html(overview, job),
        }
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
        },
        {
            'title': '底稿报送提醒',
            'description': '上传底稿目录表，查看归档流程、逾期标色和协会报送截止提醒。',
            'url_name': 'manuscript_reminder',
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
