from django.db import migrations, models
import django.db.models.deletion


GROUPS = ['超级管理员', '团队负责人', '正式成员', '实习生']

ROLES = ['super_admin', 'team_lead', 'member', 'intern', 'anonymous']
ACTIONS = ['view', 'use', 'manage']

FEATURES = [
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
    'super_admin': {'*': set(ACTIONS)},
    'team_lead': {'*': {'view', 'use'}},
    'member': {
        'overview': {'view', 'use'},
        'tools': {'view', 'use'},
        'bondreminder': {'view', 'use'},
        'info': {'view', 'use'},
        'files': {'view', 'use'},
        'mistakes': {'view', 'use'},
        'interns': {'view'},
    },
    'intern': {
        'overview': {'view', 'use'},
        'tools': {'view'},
        'bondreminder': {'view'},
        'info': {'view', 'use'},
        'mistakes': {'view', 'use'},
    },
    'anonymous': {
        'overview': {'view'},
    },
}


def seed_permissions(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Feature = apps.get_model('dashboard', 'Feature')
    FeatureAccess = apps.get_model('dashboard', 'FeatureAccess')

    for group_name in GROUPS:
        Group.objects.get_or_create(name=group_name)

    feature_objects = {}
    for definition in FEATURES:
        feature, _ = Feature.objects.update_or_create(
            key=definition['key'],
            defaults={
                'name': definition['name'],
                'url_name': definition['url_name'],
                'sort_order': definition['sort_order'],
                'is_active': True,
            },
        )
        feature_objects[feature.key] = feature

    for role in ROLES:
        role_defaults = DEFAULT_ACCESS.get(role, {})
        for feature_key, feature in feature_objects.items():
            allowed_actions = role_defaults.get(feature_key, role_defaults.get('*', set()))
            for action in ACTIONS:
                FeatureAccess.objects.get_or_create(
                    feature=feature,
                    role=role,
                    action=action,
                    defaults={'allowed': action in allowed_actions},
                )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.SlugField(max_length=80, unique=True, verbose_name='功能标识')),
                ('name', models.CharField(max_length=100, verbose_name='功能名称')),
                ('url_name', models.CharField(blank=True, max_length=120, verbose_name='路由名称')),
                ('sort_order', models.PositiveIntegerField(default=100, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
            ],
            options={
                'verbose_name': '功能',
                'verbose_name_plural': '功能',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='FeatureAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('super_admin', '超级管理员'), ('team_lead', '团队负责人'), ('member', '正式成员'), ('intern', '实习生'), ('anonymous', '只读用户（未登录）')], max_length=40, verbose_name='角色')),
                ('action', models.CharField(choices=[('view', '查看'), ('use', '使用'), ('manage', '管理')], max_length=20, verbose_name='动作')),
                ('allowed', models.BooleanField(default=False, verbose_name='允许')),
                ('feature', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_rules', to='dashboard.feature', verbose_name='功能')),
            ],
            options={
                'verbose_name': '功能权限',
                'verbose_name_plural': '功能权限',
                'ordering': ['feature__sort_order', 'role', 'action'],
                'unique_together': {('feature', 'role', 'action')},
            },
        ),
        migrations.RunPython(seed_permissions, migrations.RunPython.noop),
    ]
