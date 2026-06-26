"""Feature permission helpers for the NorthTeam2 workspace."""

from django.contrib.auth.models import Group

from .models import Feature, FeatureAccess


GROUP_SUPER_ADMIN = '超级管理员'
GROUP_TEAM_LEAD = '团队负责人'
GROUP_MEMBER = '正式成员'
GROUP_INTERN = '实习生'

ROLE_GROUPS = {
    FeatureAccess.ROLE_SUPER_ADMIN: GROUP_SUPER_ADMIN,
    FeatureAccess.ROLE_TEAM_LEAD: GROUP_TEAM_LEAD,
    FeatureAccess.ROLE_MEMBER: GROUP_MEMBER,
    FeatureAccess.ROLE_INTERN: GROUP_INTERN,
}

ROLE_LABELS = dict(FeatureAccess.ROLE_CHOICES)
ACTION_LABELS = dict(FeatureAccess.ACTION_CHOICES)
ROLE_ORDER = [
    FeatureAccess.ROLE_SUPER_ADMIN,
    FeatureAccess.ROLE_TEAM_LEAD,
    FeatureAccess.ROLE_MEMBER,
    FeatureAccess.ROLE_INTERN,
    FeatureAccess.ROLE_ANONYMOUS,
]
ACTION_ORDER = [
    FeatureAccess.ACTION_VIEW,
    FeatureAccess.ACTION_USE,
    FeatureAccess.ACTION_MANAGE,
]

FEATURE_DEFINITIONS = [
    {'key': 'overview', 'name': '概况', 'url_name': 'dashboard:home', 'sort_order': 10},
    {'key': 'projects', 'name': '项目空间', 'url_name': 'dashboard:projects', 'sort_order': 20},
    {'key': 'tools', 'name': '高效工具箱', 'url_name': 'dashboard:tools', 'sort_order': 30},
    {'key': 'bondreminder', 'name': '付息兑付提醒', 'url_name': 'bond_reminder', 'sort_order': 31},
    {'key': 'info', 'name': '常用信息', 'url_name': 'dashboard:info', 'sort_order': 40},
    {'key': 'files', 'name': '文件共享空间', 'url_name': 'dashboard:files', 'sort_order': 50},
    {'key': 'mistakes', 'name': '错题本', 'url_name': 'dashboard:mistakes', 'sort_order': 60},
    {'key': 'interns', 'name': '实习生登记', 'url_name': 'dashboard:interns', 'sort_order': 70},
    {'key': 'access_control', 'name': '权限控制台', 'url_name': 'access_control', 'sort_order': 900},
]

DEFAULT_ACCESS = {
    FeatureAccess.ROLE_SUPER_ADMIN: {
        '*': set(ACTION_ORDER),
    },
    FeatureAccess.ROLE_TEAM_LEAD: {
        '*': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
    },
    FeatureAccess.ROLE_MEMBER: {
        'overview': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
        'tools': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
        'bondreminder': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
        'info': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
        'files': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
        'mistakes': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
        'interns': {FeatureAccess.ACTION_VIEW},
    },
    FeatureAccess.ROLE_INTERN: {
        'overview': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
        'tools': {FeatureAccess.ACTION_VIEW},
        'bondreminder': {FeatureAccess.ACTION_VIEW},
        'info': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
        'mistakes': {FeatureAccess.ACTION_VIEW, FeatureAccess.ACTION_USE},
    },
    FeatureAccess.ROLE_ANONYMOUS: {
        'overview': {FeatureAccess.ACTION_VIEW},
    },
}


def sync_default_permissions():
    """Create default groups, features, and missing access rows."""
    for group_name in ROLE_GROUPS.values():
        Group.objects.get_or_create(name=group_name)

    features = {}
    for definition in FEATURE_DEFINITIONS:
        feature, _ = Feature.objects.update_or_create(
            key=definition['key'],
            defaults={
                'name': definition['name'],
                'url_name': definition.get('url_name', ''),
                'sort_order': definition.get('sort_order', 100),
                'is_active': definition.get('is_active', True),
            },
        )
        features[feature.key] = feature

    for role in ROLE_ORDER:
        role_defaults = DEFAULT_ACCESS.get(role, {})
        for feature_key, feature in features.items():
            allowed_actions = role_defaults.get(feature_key, role_defaults.get('*', set()))
            for action in ACTION_ORDER:
                FeatureAccess.objects.get_or_create(
                    feature=feature,
                    role=role,
                    action=action,
                    defaults={'allowed': action in allowed_actions},
                )


def role_for_user(user):
    if not user.is_authenticated:
        return FeatureAccess.ROLE_ANONYMOUS
    if user.is_superuser or user.groups.filter(name=GROUP_SUPER_ADMIN).exists():
        return FeatureAccess.ROLE_SUPER_ADMIN
    if user.groups.filter(name=GROUP_TEAM_LEAD).exists():
        return FeatureAccess.ROLE_TEAM_LEAD
    if user.groups.filter(name=GROUP_MEMBER).exists():
        return FeatureAccess.ROLE_MEMBER
    if user.groups.filter(name=GROUP_INTERN).exists():
        return FeatureAccess.ROLE_INTERN
    return FeatureAccess.ROLE_ANONYMOUS


def is_super_admin(user):
    return user.is_authenticated and role_for_user(user) == FeatureAccess.ROLE_SUPER_ADMIN


def has_feature_access(user, feature_key, action=FeatureAccess.ACTION_VIEW):
    if user.is_authenticated and user.is_superuser:
        return True
    role = role_for_user(user)
    return FeatureAccess.objects.filter(
        feature__key=feature_key,
        feature__is_active=True,
        role=role,
        action=action,
        allowed=True,
    ).exists()


def features_for_user(user, action=FeatureAccess.ACTION_VIEW):
    role = role_for_user(user)
    if user.is_authenticated and user.is_superuser:
        return Feature.objects.filter(is_active=True).order_by('sort_order', 'id')
    return Feature.objects.filter(
        is_active=True,
        access_rules__role=role,
        access_rules__action=action,
        access_rules__allowed=True,
    ).distinct().order_by('sort_order', 'id')
