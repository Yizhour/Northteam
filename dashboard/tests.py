import json

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import Feature, FeatureAccess


class DashboardPageTests(TestCase):
    def user_in_group(self, username, group_name, **kwargs):
        user = User.objects.create_user(username=username, password='pass12345', **kwargs)
        user.groups.add(Group.objects.get(name=group_name))
        return user

    def test_default_permissions_are_seeded(self):
        self.assertTrue(Group.objects.filter(name='超级管理员').exists())
        self.assertTrue(Group.objects.filter(name='团队负责人').exists())
        self.assertTrue(Group.objects.filter(name='正式成员').exists())
        self.assertTrue(Group.objects.filter(name='实习生').exists())
        self.assertFalse(Group.objects.filter(name='只读用户（未登录）').exists())
        self.assertTrue(Feature.objects.filter(key='bondreminder').exists())
        self.assertTrue(
            FeatureAccess.objects.filter(
                feature__key='overview',
                role=FeatureAccess.ROLE_ANONYMOUS,
                action=FeatureAccess.ACTION_VIEW,
                allowed=True,
            ).exists()
        )

    def test_anonymous_user_can_only_view_overview(self):
        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NorthTeam 工作台')
        self.assertContains(response, '登录')
        self.assertNotContains(response, '高效工具箱')

        tools_response = self.client.get(reverse('dashboard:tools'))
        self.assertEqual(tools_response.status_code, 302)
        self.assertIn('/accounts/login/', tools_response['Location'])

    def test_member_navigation_and_pages_follow_permissions(self):
        self.user_in_group('member', '正式成员')
        self.client.login(username='member', password='pass12345')

        response = self.client.get(reverse('dashboard:tools'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '高效工具箱')
        self.assertContains(response, '付息兑付提醒')
        self.assertContains(response, 'member')
        self.assertNotContains(response, '权限控制台')

        interns_response = self.client.get(reverse('dashboard:interns'))
        self.assertEqual(interns_response.status_code, 200)

    def test_intern_can_view_bondreminder_but_cannot_use_mutating_api(self):
        self.user_in_group('intern', '实习生')
        self.client.login(username='intern', password='pass12345')

        page = self.client.get('/tools/bond-reminder/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'NorthTeam 工作台')
        self.assertContains(page, 'systemTitle')

        get_response = self.client.get('/tools/bond-reminder/api/config')
        self.assertEqual(get_response.status_code, 200)
        self.assertTrue(json.loads(get_response.content)['ok'])

        post_response = self.client.post(
            '/tools/bond-reminder/api/config',
            data=json.dumps({'weekly_enabled': False}),
            content_type='application/json',
        )
        self.assertEqual(post_response.status_code, 403)
        self.assertFalse(json.loads(post_response.content)['ok'])

    def test_member_can_use_bondreminder_api(self):
        self.user_in_group('member_api', '正式成员')
        self.client.login(username='member_api', password='pass12345')

        response = self.client.get('/tools/bond-reminder/api/health')
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['status'], 'running')

    def test_super_admin_can_open_access_control_and_admin(self):
        User.objects.create_superuser('root', 'root@example.com', 'pass12345')
        self.client.login(username='root', password='pass12345')

        access_response = self.client.get(reverse('access_control'))
        self.assertEqual(access_response.status_code, 200)
        self.assertContains(access_response, '权限控制台')
        self.assertContains(access_response, '超级管理员')

        admin_response = self.client.get(reverse('admin:index'))
        self.assertEqual(admin_response.status_code, 200)

    def test_super_admin_group_can_open_access_control_without_staff_flag(self):
        self.user_in_group('group_admin', '超级管理员')
        self.client.login(username='group_admin', password='pass12345')

        response = self.client.get(reverse('access_control'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '权限控制台')

    def test_non_super_admin_cannot_open_access_control(self):
        self.user_in_group('lead', '团队负责人', is_staff=True)
        self.client.login(username='lead', password='pass12345')

        response = self.client.get(reverse('access_control'))
        self.assertEqual(response.status_code, 403)

    def test_login_page_is_available(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NorthTeam 工作台')
        self.assertContains(response, '登录')
