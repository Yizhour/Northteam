from django.db import migrations


def disable_anonymous_feature_access(apps, schema_editor):
    FeatureAccess = apps.get_model('dashboard', 'FeatureAccess')
    FeatureAccess.objects.filter(role='anonymous').update(allowed=False)


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0006_fill_user_names'),
    ]

    operations = [
        migrations.RunPython(disable_anonymous_feature_access, migrations.RunPython.noop),
    ]
