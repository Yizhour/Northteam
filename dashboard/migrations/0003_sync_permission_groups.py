from django.db import migrations


def sync_permission_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Feature = apps.get_model('dashboard', 'Feature')
    FeatureAccess = apps.get_model('dashboard', 'FeatureAccess')

    for group_name in ['超级管理员', '团队负责人', '正式成员', '实习生']:
        Group.objects.get_or_create(name=group_name)

    feature, _ = Feature.objects.update_or_create(
        key='interns',
        defaults={
            'name': '实习生登记',
            'url_name': 'dashboard:interns',
            'sort_order': 70,
            'is_active': True,
        },
    )
    access = {
        'super_admin': {'view', 'use', 'manage'},
        'team_lead': {'view', 'use'},
        'member': {'view', 'use'},
        'intern': {'view', 'use'},
        'anonymous': set(),
    }
    for role, allowed_actions in access.items():
        for action in ['view', 'use', 'manage']:
            FeatureAccess.objects.update_or_create(
                feature=feature,
                role=role,
                action=action,
                defaults={'allowed': action in allowed_actions},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_internschedule'),
    ]

    operations = [
        migrations.RunPython(sync_permission_groups, migrations.RunPython.noop),
    ]
