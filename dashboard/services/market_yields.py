import time
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from dashboard.models import MarketYieldPoint
from dashboard.services.file_locks import file_lock


BASE_URL = 'https://yield.chinabond.com.cn/cbweb-mn'
FETCH_LOCK_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class CurveTarget:
    code: str
    name: str
    full_name: str


TARGET_CURVES = [
    CurveTarget('treasury', '国债', '中债国债收益率曲线'),
    CurveTarget('aaa_cp', 'AAA中短期票据', '中债中短期票据收益率曲线(AAA)'),
    CurveTarget('aa_plus_cp', 'AA+中短期票据', '中债中短期票据收益率曲线(AA＋)'),
]
RETENTION_TRADING_DAYS = 30

TARGET_MATURITIES = [
    (Decimal('1.00'), '1Y'),
    (Decimal('2.00'), '2Y'),
    (Decimal('3.00'), '3Y'),
    (Decimal('5.00'), '5Y'),
    (Decimal('10.00'), '10Y'),
]


def make_session():
    import requests

    session = requests.Session()
    session.headers.update(
        {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/126.0.0.0 Safari/537.36'
            ),
            'Referer': f'{BASE_URL}/yield_main?locale=zh_CN',
            'Accept': 'application/json, text/plain, */*',
        }
    )
    return session


def normalize_name(value):
    text = unicodedata.normalize('NFKC', str(value or ''))
    return ''.join(text.split())


def iter_tree_items(items):
    for item in items or []:
        yield item
        for child_key in ('children', 'childList', 'nodes'):
            children = item.get(child_key)
            if children:
                yield from iter_tree_items(children)


def query_curve_tree(session):
    response = session.get(f'{BASE_URL}/yc/queryTree', params={'locale': 'zh_CN'}, timeout=20)
    response.raise_for_status()
    curve_map = {}
    for item in iter_tree_items(response.json()):
        name = item.get('name') or item.get('text')
        curve_id = item.get('id') or item.get('value')
        if name and curve_id:
            curve_map[str(name)] = str(curve_id)
    return curve_map


def find_curve_id(curve_map, target):
    if target.full_name in curve_map:
        return curve_map[target.full_name]

    normalized_target = normalize_name(target.full_name)
    for name, curve_id in curve_map.items():
        normalized_name = normalize_name(name)
        if normalized_name == normalized_target:
            return curve_id

    raise ValueError(f'未找到中债曲线：{target.full_name}')


def query_yield_curve(session, curve_id, date_str):
    params = {
        'xyzSelect': 'txy',
        'workTimes': date_str,
        'dxbj': '4',
        'qxll': '1,',
        'yqqxN': 'N',
        'yqqxK': 'K',
        'ycDefIds': f'{curve_id},',
        'locale': 'zh_CN',
    }
    response = session.post(f'{BASE_URL}/yc/searchXyFxsyl', params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    chart_list = data.get('ycChartDataList') or []
    if not chart_list:
        return []

    item = chart_list[0]
    rows = []
    curve_full_name = item.get('ycDefName') or ''
    worktime = str(item.get('worktime') or date_str)[:10]
    series = item.get('seriesData') or []
    target_by_year = {years: label for years, label in TARGET_MATURITIES}

    for point in series:
        if len(point) < 2:
            continue
        try:
            maturity = Decimal(str(point[0])).quantize(Decimal('0.01'))
            yield_rate = Decimal(str(point[1])).quantize(Decimal('0.0001'))
        except (InvalidOperation, TypeError, ValueError):
            continue
        maturity_label = target_by_year.get(maturity)
        if maturity_label:
            rows.append(
                {
                    'trading_date': worktime,
                    'curve_full_name': curve_full_name,
                    'maturity_years': maturity,
                    'maturity_label': maturity_label,
                    'yield_rate': yield_rate,
                }
            )
    return rows


def fetch_recent_market_yields(min_trading_days=2, lookback_days=14, sleep_seconds=0.25):
    with file_lock('market-yields-fetch', FETCH_LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            return {'ok': False, 'message': '收益率更新正在执行，请稍后再试。', 'saved': 0, 'dates': []}
        try:
            return _fetch_recent_market_yields(min_trading_days, lookback_days, sleep_seconds)
        except Exception as exc:
            return {'ok': False, 'message': f'收益率数据更新失败：{exc}', 'saved': 0, 'dates': []}


def _fetch_recent_market_yields(min_trading_days, lookback_days, sleep_seconds):
    session = make_session()
    curve_map = query_curve_tree(session)
    selected = [(target, find_curve_id(curve_map, target)) for target in TARGET_CURVES]

    today = timezone.localdate()
    saved_count = 0
    trading_dates = []
    fetched_at = timezone.now()

    for offset in range(lookback_days + 1):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        day_rows = []
        for target, curve_id in selected:
            rows = query_yield_curve(session, curve_id, day.isoformat())
            for row in rows:
                row['curve_code'] = target.code
                row['curve_name'] = target.name
                if not row['curve_full_name']:
                    row['curve_full_name'] = target.full_name
            day_rows.extend(rows)
            time.sleep(sleep_seconds)

        if not day_rows:
            continue

        with transaction.atomic():
            for row in day_rows:
                point, _ = MarketYieldPoint.objects.update_or_create(
                    source=MarketYieldPoint.SOURCE_CHINABOND,
                    curve_code=row['curve_code'],
                    trading_date=row['trading_date'],
                    maturity_years=row['maturity_years'],
                    defaults={
                        'curve_name': row['curve_name'],
                        'curve_full_name': row['curve_full_name'],
                        'maturity_label': row['maturity_label'],
                        'yield_rate': row['yield_rate'],
                        'fetched_at': fetched_at,
                    },
                )
                saved_count += 1

        date_key = str(day)
        if date_key not in trading_dates:
            trading_dates.append(date_key)
        if len(trading_dates) >= min_trading_days:
            break

    if not trading_dates:
        return {'ok': False, 'message': '未抓取到最近交易日收益率数据。', 'saved': 0, 'dates': []}

    deleted_count = prune_old_market_yields()
    return {
        'ok': True,
        'message': '收益率数据已更新。',
        'saved': saved_count,
        'deleted': deleted_count,
        'dates': trading_dates,
    }


def prune_old_market_yields(retention_trading_days=RETENTION_TRADING_DAYS):
    keep_dates = list(
        MarketYieldPoint.objects.filter(source=MarketYieldPoint.SOURCE_CHINABOND)
        .order_by('-trading_date')
        .values_list('trading_date', flat=True)
        .distinct()[:retention_trading_days]
    )
    if len(keep_dates) < retention_trading_days:
        return 0
    deleted_count, _ = (
        MarketYieldPoint.objects.filter(source=MarketYieldPoint.SOURCE_CHINABOND)
        .exclude(trading_date__in=keep_dates)
        .delete()
    )
    return deleted_count


def format_rate(rate):
    return f'{Decimal(rate).quantize(Decimal("0.01"))}%'


def format_change(current, previous):
    if previous is None:
        return {'class': 'neutral', 'display': f'{format_rate(current)}'}
    bp = int(((Decimal(current) - Decimal(previous)) * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    if bp > 0:
        return {'class': 'up', 'display': f'{format_rate(current)}（↑ {bp}BP）'}
    if bp < 0:
        return {'class': 'down', 'display': f'{format_rate(current)}（↓ {abs(bp)}BP）'}
    return {'class': 'flat', 'display': f'{format_rate(current)}（→ 0BP）'}


def market_yield_overview():
    dates = list(
        MarketYieldPoint.objects.filter(source=MarketYieldPoint.SOURCE_CHINABOND)
        .order_by('-trading_date')
        .values_list('trading_date', flat=True)
        .distinct()[:2]
    )
    latest_date = dates[0] if dates else None
    previous_date = dates[1] if len(dates) > 1 else None

    points = {}
    if latest_date:
        for point in MarketYieldPoint.objects.filter(
            source=MarketYieldPoint.SOURCE_CHINABOND,
            trading_date__in=[date for date in dates if date],
        ):
            points[(point.trading_date, point.curve_code, point.maturity_years)] = point

    rows = []
    latest_points = []
    for target in TARGET_CURVES:
        cells = []
        for maturity_years, maturity_label in TARGET_MATURITIES:
            current = points.get((latest_date, target.code, maturity_years)) if latest_date else None
            previous = points.get((previous_date, target.code, maturity_years)) if previous_date else None
            if current:
                latest_points.append(current)
                formatted = format_change(current.yield_rate, previous.yield_rate if previous else None)
                cells.append(
                    {
                        'maturity': maturity_label,
                        'display': formatted['display'],
                        'direction': formatted['class'],
                    }
                )
            else:
                cells.append({'maturity': maturity_label, 'display': '--', 'direction': 'neutral'})
        rows.append({'curve': target.name, 'cells': cells})

    updated_at = max((point.fetched_at for point in latest_points), default=None)
    return {
        'available': bool(latest_date),
        'latest_date': latest_date,
        'previous_date': previous_date,
        'updated_at': timezone.localtime(updated_at) if updated_at else None,
        'maturities': [label for _, label in TARGET_MATURITIES],
        'rows': rows,
    }
