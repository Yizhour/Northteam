from django.db import models


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
