from django.db import migrations


FEATURE = {
    'key': 'manuscriptreminder',
    'name': '底稿报送提醒',
    'url_name': 'manuscript_reminder',
    'sort_order': 32,
}

ACTIONS = ['view', 'use', 'manage']
DEFAULT_ACCESS = {
    'super_admin': set(ACTIONS),
    'team_lead': {'view', 'use'},
    'member': {'view', 'use'},
    'intern': set(),
    'anonymous': set(),
}


def seed_feature(apps, schema_editor):
    Feature = apps.get_model('dashboard', 'Feature')
    FeatureAccess = apps.get_model('dashboard', 'FeatureAccess')
    feature, _ = Feature.objects.update_or_create(
        key=FEATURE['key'],
        defaults={
            'name': FEATURE['name'],
            'url_name': FEATURE['url_name'],
            'sort_order': FEATURE['sort_order'],
            'is_active': True,
        },
    )
    for role, allowed_actions in DEFAULT_ACCESS.items():
        for action in ACTIONS:
            FeatureAccess.objects.get_or_create(
                feature=feature,
                role=role,
                action=action,
                defaults={'allowed': action in allowed_actions},
            )


class Migration(migrations.Migration):
    dependencies = [
        ('dashboard', '0012_infocard_infocarditem_infocardpermission_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_feature, migrations.RunPython.noop),
    ]
