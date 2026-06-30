from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0007_disable_anonymous_feature_access'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketYieldPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(default='chinabond', max_length=40)),
                ('curve_code', models.CharField(max_length=40)),
                ('curve_name', models.CharField(max_length=120)),
                ('curve_full_name', models.CharField(blank=True, max_length=200)),
                ('trading_date', models.DateField(db_index=True)),
                ('maturity_label', models.CharField(max_length=8)),
                ('maturity_years', models.DecimalField(decimal_places=2, max_digits=5)),
                ('yield_rate', models.DecimalField(decimal_places=4, max_digits=8)),
                ('fetched_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-trading_date', 'curve_code', 'maturity_years'],
                'unique_together': {('source', 'curve_code', 'trading_date', 'maturity_years')},
            },
        ),
        migrations.AddIndex(
            model_name='marketyieldpoint',
            index=models.Index(fields=['source', '-trading_date'], name='dashboard_m_source_9118f1_idx'),
        ),
        migrations.AddIndex(
            model_name='marketyieldpoint',
            index=models.Index(fields=['curve_code', '-trading_date'], name='dashboard_m_curve_c_4e8c90_idx'),
        ),
    ]
