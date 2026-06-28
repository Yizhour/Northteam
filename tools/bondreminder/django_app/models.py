from django.db import models


class BondReminderStore(models.Model):
    key = models.CharField('数据键', max_length=80, unique=True)
    value = models.JSONField('数据内容', default=dict, blank=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = '付息兑付配置数据'
        verbose_name_plural = '付息兑付配置数据'

    def __str__(self):
        return self.key


class BondReminderTableRow(models.Model):
    TABLE_BOND = 'bond'
    TABLE_CUSTOMER = 'customer'
    TABLE_CHOICES = [
        (TABLE_BOND, '付息兑付表'),
        (TABLE_CUSTOMER, '客户表'),
    ]

    table_key = models.CharField('表类型', max_length=40, choices=TABLE_CHOICES)
    row_index = models.PositiveIntegerField('行号')
    data = models.JSONField('行数据', default=dict, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        unique_together = [('table_key', 'row_index')]
        ordering = ['table_key', 'row_index']
        verbose_name = '付息兑付表格行'
        verbose_name_plural = '付息兑付表格行'

    def __str__(self):
        return f'{self.get_table_key_display()} #{self.row_index}'
