from django.db import migrations


def fill_user_names(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    for user in User.objects.all():
        first_name = (user.first_name or '').strip()
        last_name = (user.last_name or '').strip()
        if first_name or last_name:
            continue
        user.first_name = user.username
        user.save(update_fields=['first_name'])


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('dashboard', '0005_remove_legacy_intern_group'),
    ]

    operations = [
        migrations.RunPython(fill_user_names, migrations.RunPython.noop),
    ]
