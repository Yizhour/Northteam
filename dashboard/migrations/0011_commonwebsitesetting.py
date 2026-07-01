from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0010_commonwebsite'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommonWebsiteSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default='default', max_length=40, unique=True)),
                ('cards_per_row', models.PositiveSmallIntegerField(default=3, verbose_name='每行卡片数')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '常用网站设置',
                'verbose_name_plural': '常用网站设置',
                'ordering': ['key'],
            },
        ),
    ]
