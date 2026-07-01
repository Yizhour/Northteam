from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0008_marketyieldpoint'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketYieldRefreshJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default='default', max_length=40, unique=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('idle', 'Idle'),
                            ('running', 'Running'),
                            ('success', 'Success'),
                            ('failed', 'Failed'),
                        ],
                        default='idle',
                        max_length=20,
                    ),
                ),
                ('message', models.CharField(blank=True, max_length=500)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('requested_by', models.CharField(blank=True, max_length=150)),
                ('trigger', models.CharField(blank=True, max_length=40)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['key'],
            },
        ),
    ]
