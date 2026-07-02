from django.db import models


class ManuscriptReminderStore(models.Model):
    key = models.CharField('数据键', max_length=80, unique=True)
    value = models.JSONField('数据内容', default=dict, blank=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = '底稿报送配置数据'
        verbose_name_plural = '底稿报送配置数据'

    def __str__(self):
        return self.key


class ManuscriptReminderTableRow(models.Model):
    row_index = models.PositiveIntegerField('行号')
    data = models.JSONField('行数据', default=dict, blank=True)
    style = models.JSONField('样式元数据', default=dict, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['row_index']
        verbose_name = '底稿报送表格行'
        verbose_name_plural = '底稿报送表格行'

    def __str__(self):
        return f'底稿报送表格行 #{self.row_index}'


class ManuscriptReminderLog(models.Model):
    line = models.TextField('运行日志')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = '底稿报送运行日志'
        verbose_name_plural = '底稿报送运行日志'

    def __str__(self):
        return self.line[:80]
