from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ManuscriptReminderLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('line', models.TextField(verbose_name='运行日志')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '底稿报送运行日志',
                'verbose_name_plural': '底稿报送运行日志',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='ManuscriptReminderStore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=80, unique=True, verbose_name='数据键')),
                ('value', models.JSONField(blank=True, default=dict, verbose_name='数据内容')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '底稿报送配置数据',
                'verbose_name_plural': '底稿报送配置数据',
                'ordering': ['key'],
            },
        ),
        migrations.CreateModel(
            name='ManuscriptReminderTableRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row_index', models.PositiveIntegerField(verbose_name='行号')),
                ('data', models.JSONField(blank=True, default=dict, verbose_name='行数据')),
                ('style', models.JSONField(blank=True, default=dict, verbose_name='样式元数据')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '底稿报送表格行',
                'verbose_name_plural': '底稿报送表格行',
                'ordering': ['row_index'],
            },
        ),
    ]
