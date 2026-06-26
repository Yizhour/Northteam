import json

from django.test import TestCase
from django.urls import reverse


class DashboardPageTests(TestCase):
    def test_home_page_renders_workspace_overview(self):
        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NorthTeam 工作台')
        self.assertContains(response, '团队内部管理概况')

    def test_placeholder_pages_render_navigation_targets(self):
        page_names = [
            ('dashboard:projects', '项目空间'),
            ('dashboard:info', '常用信息'),
            ('dashboard:files', '文件共享空间'),
            ('dashboard:mistakes', '错题本'),
            ('dashboard:interns', '实习生登记'),
        ]

        for url_name, title in page_names:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, title)
                self.assertContains(response, '功能预留')

    def test_tools_page_links_to_bond_reminder(self):
        response = self.client.get(reverse('dashboard:tools'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '高效工具箱')
        self.assertContains(response, '付息兑付提醒')
        self.assertContains(response, '/tools/bond-reminder/')

    def test_bond_reminder_flask_tool_is_mounted(self):
        response = self.client.get('/tools/bond-reminder/api/health')
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['status'], 'running')

    def test_admin_login_is_available(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])
