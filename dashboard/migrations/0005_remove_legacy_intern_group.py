from django.db import migrations


def remove_legacy_intern_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='实习生').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_intern_alter_internschedule_intern'),
    ]

    operations = [
        migrations.RunPython(remove_legacy_intern_group, migrations.RunPython.noop),
    ]
