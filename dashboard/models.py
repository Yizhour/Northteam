from datetime import time
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Feature(models.Model):
    """A configurable feature entry shown in the workspace."""

    key = models.SlugField('功能标识', max_length=80, unique=True)
    name = models.CharField('功能名称', max_length=100)
    url_name = models.CharField('路由名称', max_length=120, blank=True)
    sort_order = models.PositiveIntegerField('排序', default=100)
    is_active = models.BooleanField('启用', default=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = '功能'
        verbose_name_plural = '功能'

    def __str__(self):
        return self.name


class FeatureAccess(models.Model):
    """Role-based access rule for a feature and action."""

    ROLE_SUPER_ADMIN = 'super_admin'
    ROLE_TEAM_LEAD = 'team_lead'
    ROLE_MEMBER = 'member'
    ROLE_INTERN = 'intern'
    ROLE_ANONYMOUS = 'anonymous'

    ACTION_VIEW = 'view'
    ACTION_USE = 'use'
    ACTION_MANAGE = 'manage'

    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, '超级管理员'),
        (ROLE_TEAM_LEAD, '团队负责人'),
        (ROLE_MEMBER, '正式成员'),
        (ROLE_INTERN, '实习生'),
        (ROLE_ANONYMOUS, '只读用户（未登录）'),
    ]
    ACTION_CHOICES = [
        (ACTION_VIEW, '查看'),
        (ACTION_USE, '使用'),
        (ACTION_MANAGE, '管理'),
    ]

    feature = models.ForeignKey(Feature, verbose_name='功能', on_delete=models.CASCADE, related_name='access_rules')
    role = models.CharField('角色', max_length=40, choices=ROLE_CHOICES)
    action = models.CharField('动作', max_length=20, choices=ACTION_CHOICES)
    allowed = models.BooleanField('允许', default=False)

    class Meta:
        unique_together = [('feature', 'role', 'action')]
        ordering = ['feature__sort_order', 'role', 'action']
        verbose_name = '功能权限'
        verbose_name_plural = '功能权限'

    def __str__(self):
        return f'{self.feature} - {self.get_role_display()} - {self.get_action_display()}'


def make_intern_access_token():
    return secrets.token_urlsafe(24)


def format_local_range(start_time, end_time):
    local_start = timezone.localtime(start_time)
    local_end = timezone.localtime(end_time)
    return f'{local_start:%Y-%m-%d %H:%M}-{local_end:%H:%M}'


class Intern(models.Model):
    """Standalone intern profile with a private schedule access link."""

    name = models.CharField('姓名', max_length=80)
    note = models.CharField('备注', max_length=200, blank=True)
    access_token = models.CharField('专属链接令牌', max_length=80, unique=True, default=make_intern_access_token)
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        verbose_name = '实习生'
        verbose_name_plural = '实习生'

    def __str__(self):
        return self.name


class InternSchedule(models.Model):
    """Work or leave time reserved on an intern's weekly schedule."""

    TYPE_WORK = 'work'
    TYPE_LEAVE = 'leave'
    TYPE_CHOICES = [
        (TYPE_WORK, '工作安排'),
        (TYPE_LEAVE, '请假'),
    ]

    intern = models.ForeignKey(
        Intern,
        verbose_name='实习生',
        on_delete=models.CASCADE,
        related_name='intern_schedules',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='安排人',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_intern_schedules',
    )
    schedule_type = models.CharField('类型', max_length=20, choices=TYPE_CHOICES, default=TYPE_WORK)
    title = models.CharField('工作标题', max_length=120)
    notes = models.TextField('备注', blank=True)
    start_time = models.DateTimeField('开始时间')
    end_time = models.DateTimeField('结束时间')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['start_time', 'id']
        verbose_name = '实习生工作安排'
        verbose_name_plural = '实习生工作安排'

    def __str__(self):
        return f'{self.intern} - {self.title}'

    def clean(self):
        errors = {}
        if self.start_time and timezone.is_naive(self.start_time):
            self.start_time = timezone.make_aware(self.start_time)
        if self.end_time and timezone.is_naive(self.end_time):
            self.end_time = timezone.make_aware(self.end_time)

        if self.start_time and self.end_time:
            local_start = timezone.localtime(self.start_time)
            local_end = timezone.localtime(self.end_time)
            if self.end_time <= self.start_time:
                errors['end_time'] = '结束时间必须大于开始时间。'
            if local_start.date() != local_end.date():
                errors['end_time'] = '工作安排不能跨天。'
            work_start = time(9, 0)
            work_end = time(18, 0)
            lunch_start = time(12, 0)
            lunch_end = time(13, 30)
            if local_start.time() < work_start or local_end.time() > work_end:
                errors['start_time'] = '工作安排时间必须在 9:00-18:00 之间。'
            if local_start.time() < lunch_end and local_end.time() > lunch_start:
                errors['start_time'] = '12:00-13:30 为午休时间，不能安排工作或请假。'

        if self.intern_id and self.start_time and self.end_time:
            conflicts = InternSchedule.objects.filter(
                intern=self.intern,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            conflict = conflicts.order_by('start_time', 'id').first()
            if conflict:
                overlap_start = max(self.start_time, conflict.start_time)
                overlap_end = min(self.end_time, conflict.end_time)
                errors['start_time'] = (
                    f'该时间段已有安排：{conflict.title}（{format_local_range(conflict.start_time, conflict.end_time)}）；'
                    f'重叠时间：{format_local_range(overlap_start, overlap_end)}。'
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
