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
            ('dashboard:tools', '高效工具箱'),
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

    def test_admin_login_is_available(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])
