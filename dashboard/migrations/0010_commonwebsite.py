from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0009_marketyieldrefreshjob'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommonWebsite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='网站名')),
                ('url', models.URLField(max_length=500, verbose_name='网站链接')),
                ('sort_order', models.PositiveIntegerField(default=100, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '常用网站',
                'verbose_name_plural': '常用网站',
                'ordering': ['sort_order', 'name', 'id'],
            },
        ),
    ]
