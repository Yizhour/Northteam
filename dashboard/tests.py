import json
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from tools.bondreminder.app.bond_logic import BondReminder
from tools.bondreminder.app.config import BOND_CACHE_FILE
from tools.bondreminder.app.storage import save_bond_table_from_upload

from .models import Feature, FeatureAccess, Intern, InternSchedule


class DashboardPageTests(TestCase):
    def user_in_group(self, username, group_name, **kwargs):
        kwargs.setdefault('first_name', username)
        user = User.objects.create_user(username=username, password='pass12345', **kwargs)
        user.groups.add(Group.objects.get(name=group_name))
        return user

    def schedule_day(self):
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat()

    def schedule_payload(self, intern, start='09:00', end='10:00', title='整理材料'):
        day = self.schedule_day()
        return {
            'intern_id': intern.id,
            'schedule_type': InternSchedule.TYPE_WORK,
            'title': title,
            'start_time': f'{day}T{start}:00',
            'end_time': f'{day}T{end}:00',
        }

    def weekend_day(self):
        return (datetime.fromisoformat(self.schedule_day()).date() + timedelta(days=5)).isoformat()

    def test_default_permissions_are_seeded(self):
        self.assertTrue(Group.objects.filter(name='超级管理员').exists())
        self.assertTrue(Group.objects.filter(name='团队负责人').exists())
        self.assertTrue(Group.objects.filter(name='正式成员').exists())
        self.assertFalse(Group.objects.filter(name='实习生').exists())
        self.assertFalse(Group.objects.filter(name='只读用户（未登录）').exists())
        self.assertTrue(Feature.objects.filter(key='bondreminder').exists())
        self.assertFalse(
            FeatureAccess.objects.filter(
                feature__key='overview',
                role=FeatureAccess.ROLE_ANONYMOUS,
                action=FeatureAccess.ACTION_VIEW,
                allowed=True,
            ).exists()
        )

    def test_anonymous_user_is_redirected_to_login_for_dashboard(self):
        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

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

    def test_user_without_role_cannot_open_bondreminder(self):
        User.objects.create_user(username='no_role', first_name='no_role', password='pass12345')
        self.client.login(username='no_role', password='pass12345')

        page = self.client.get('/tools/bond-reminder/')
        self.assertEqual(page.status_code, 403)

        get_response = self.client.get('/tools/bond-reminder/api/config')
        self.assertEqual(get_response.status_code, 403)
        self.assertFalse(json.loads(get_response.content)['ok'])

    def test_member_can_use_bondreminder_api(self):
        self.user_in_group('member_api', '正式成员')
        self.client.login(username='member_api', password='pass12345')

        response = self.client.get('/tools/bond-reminder/api/health')
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['status'], 'running')

    def test_bondreminder_upload_button_is_removed(self):
        self.user_in_group('bond_upload_page_member', '正式成员')
        self.client.login(username='bond_upload_page_member', password='pass12345')

        response = self.client.get('/tools/bond-reminder/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="bondFile"')
        self.assertNotContains(response, 'id="uploadBondBtn"')

    def test_bondreminder_csv_upload_replaces_database_data_without_persistent_file(self):
        self.user_in_group('bond_csv_member', '正式成员')
        self.client.login(username='bond_csv_member', password='pass12345')
        self.client.delete('/tools/bond-reminder/api/logs')
        self.client.post(
            '/tools/bond-reminder/api/config',
            data=json.dumps(
                {
                    'date_columns': ['old_date_column'],
                    'display_columns': ['old_display_column'],
                    'default_column_mappings': {
                        'date_columns': ['pay_date'],
                        'display_columns': ['code', 'pay_date'],
                    },
                }
            ),
            content_type='application/json',
        )
        upload_dir = Path('tools/bondreminder/uploads')
        before_files = {path.name for path in upload_dir.iterdir()}
        upload = SimpleUploadedFile(
            'bonds.csv',
            b'code,pay_date\nB001,2026-06-28\n',
            content_type='text/csv',
        )

        response = self.client.post(
            '/tools/bond-reminder/api/upload/bond-data',
            data={'file': upload, 'header': '0'},
        )
        payload = json.loads(response.content)
        config_payload = json.loads(self.client.get('/tools/bond-reminder/api/config').content)
        logs_payload = json.loads(self.client.get('/tools/bond-reminder/api/logs').content)
        after_files = {path.name for path in upload_dir.iterdir()}

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['total_rows'], 1)
        self.assertEqual(payload['data']['rows'][0]['code'], 'B001')
        self.assertEqual(payload['data']['path'], 'bonds.csv')
        self.assertEqual(config_payload['data']['date_columns'], ['pay_date'])
        self.assertEqual(config_payload['data']['display_columns'], ['code', 'pay_date'])
        self.assertEqual(logs_payload['data'], [])
        self.assertEqual(after_files, before_files)

    def test_mailer_deduplicates_receivers_before_sending(self):
        from tools.bondreminder.app import mailer

        sent_receivers = []

        class FakeSMTPSSL:
            def __init__(self, *args, **kwargs):
                pass

            def login(self, sender, password):
                pass

            def sendmail(self, sender, receivers, message_bytes):
                sent_receivers.append(receivers)

            def quit(self):
                pass

            def close(self):
                pass

        mailer._last_successful_send_at = 0.0
        mailer._last_successful_candidate = None
        with patch.object(mailer.smtplib, 'SMTP_SSL', FakeSMTPSSL), patch.object(mailer.smtplib, 'SMTP') as smtp:
            result = mailer.send_mail(
                'sender@example.com',
                'secret',
                ['user@example.com', ' User@example.com ', 'other@example.com'],
                MIMEText('body', 'plain', 'utf-8'),
            )

        self.assertEqual(result['port'], 465)
        self.assertEqual(sent_receivers, [['user@example.com', 'other@example.com']])
        smtp.assert_not_called()

    def test_mailer_stops_retrying_after_delivery_attempt(self):
        from tools.bondreminder.app import mailer

        smtp_ssl_calls = []

        class TimeoutAfterDataSMTP:
            def __init__(self, *args, **kwargs):
                smtp_ssl_calls.append(args)

            def login(self, sender, password):
                pass

            def sendmail(self, sender, receivers, message_bytes):
                raise TimeoutError('timed out after DATA')

            def quit(self):
                pass

            def close(self):
                pass

        mailer._last_successful_send_at = 0.0
        mailer._last_successful_candidate = None
        with patch.object(mailer.smtplib, 'SMTP_SSL', TimeoutAfterDataSMTP), patch.object(mailer.smtplib, 'SMTP') as smtp:
            with self.assertRaises(mailer.DeliveryAttemptedError):
                mailer.send_mail(
                    'sender@example.com',
                    'secret',
                    ['user@example.com'],
                    MIMEText('body', 'plain', 'utf-8'),
                )

        self.assertEqual(len(smtp_ssl_calls), 1)
        smtp.assert_not_called()

    def test_mailer_uses_only_ssl_465(self):
        from tools.bondreminder.app import mailer

        smtp_ssl_calls = []

        class FakeSMTPSSL:
            def __init__(self, *args, **kwargs):
                smtp_ssl_calls.append(args)

            def login(self, sender, password):
                pass

            def sendmail(self, sender, receivers, message_bytes):
                pass

            def quit(self):
                pass

            def close(self):
                pass

        mailer._last_successful_send_at = 0.0
        mailer._last_successful_candidate = None
        with patch.object(mailer.smtplib, 'SMTP_SSL', FakeSMTPSSL), patch.object(mailer.smtplib, 'SMTP') as smtp:
            result = mailer.send_mail(
                'sender@example.com',
                'secret',
                ['user@example.com'],
                MIMEText('body', 'plain', 'utf-8'),
            )

        self.assertEqual(result['mode'], 'ssl')
        self.assertEqual(result['port'], 465)
        self.assertEqual(smtp_ssl_calls[0][1], 465)
        smtp.assert_not_called()

    def test_bondreminder_logs_are_persisted_and_clearable(self):
        from tools.bondreminder.app.logging_utils import append_log, clear_logs, read_logs

        clear_logs()
        first = append_log('first persistent log')
        second = append_log('second persistent log')

        self.assertEqual(read_logs(), [first, second])
        self.assertEqual(read_logs(limit=1), [second])

        clear_logs()
        self.assertEqual(read_logs(), [])

    def test_scheduler_lock_rejects_active_owner_and_accepts_stale_lock(self):
        from tools.bondreminder.app.scheduler import CrossProcessLock

        with TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / 'scheduler.lock'
            lock_path.write_text(json.dumps({'token': 'other', 'updated_at': time.time()}), encoding='utf-8')

            active_lock = CrossProcessLock(lock_path, ttl_seconds=30)
            self.assertFalse(active_lock.acquire())

            lock_path.write_text(json.dumps({'token': 'other', 'updated_at': time.time() - 60}), encoding='utf-8')
            stale_lock = CrossProcessLock(lock_path, ttl_seconds=30)
            self.assertTrue(stale_lock.acquire())
            stale_lock.release()

    def test_scheduler_refresh_rebuilds_jobs_when_config_changes(self):
        import schedule
        from tools.bondreminder.app.scheduler import SchedulerService

        service = SchedulerService()
        config_without_daily = {
            'weekly_enabled': False,
            'daily_enabled': False,
            'custom_tasks': [],
        }
        config_with_daily = {
            'weekly_enabled': False,
            'daily_enabled': True,
            'daily_time': '09:00',
            'custom_tasks': [],
        }

        try:
            with patch('tools.bondreminder.app.scheduler.load_config', side_effect=[config_without_daily, config_with_daily]):
                service.refresh_if_config_changed()
                self.assertEqual(len(schedule.jobs), 1)
                service.refresh_if_config_changed()
                self.assertEqual(len(schedule.jobs), 2)
        finally:
            schedule.clear()

    def test_super_admin_can_open_access_control_and_admin(self):
        User.objects.create_superuser('root', 'root@example.com', 'pass12345', first_name='root')
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
        self.assertContains(response, 'NorthTeam2 工作台')
        self.assertContains(response, '登录')

    def test_user_can_change_own_password(self):
        User.objects.create_user(username='password_user', first_name='password_user', password='pass12345')

        anonymous_response = self.client.get(reverse('password_change'))
        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn('/accounts/login/', anonymous_response['Location'])

        self.client.login(username='password_user', password='pass12345')
        page_response = self.client.get(reverse('password_change'))
        self.assertEqual(page_response.status_code, 200)

        change_response = self.client.post(
            reverse('password_change'),
            data={
                'old_password': 'pass12345',
                'new_password1': 'BetterPass12345!',
                'new_password2': 'BetterPass12345!',
            },
        )

        self.assertEqual(change_response.status_code, 302)
        self.assertEqual(change_response['Location'], reverse('password_change_done'))
        self.client.logout()
        self.assertFalse(self.client.login(username='password_user', password='pass12345'))
        self.assertTrue(self.client.login(username='password_user', password='BetterPass12345!'))

    def test_vue_session_api_returns_no_anonymous_navigation(self):
        response = self.client.get('/api/session/')
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertFalse(payload['data']['authenticated'])
        self.assertEqual(payload['data']['features'], [])

    def test_admin_user_creation_requires_name(self):
        from .admin import RequiredNameUserCreationForm

        form = RequiredNameUserCreationForm(
            data={
                'username': 'missing_name',
                'password1': 'StrongPass12345!',
                'password2': 'StrongPass12345!',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)

    def test_vue_login_api_returns_member_navigation(self):
        self.user_in_group('vue_member', '正式成员')

        response = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'vue_member', 'password': 'pass12345'}),
            content_type='application/json',
        )
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['data']['authenticated'])
        self.assertEqual(payload['data']['username'], 'vue_member')
        self.assertIn('tools', [item['key'] for item in payload['data']['features']])

    def test_vue_tools_api_respects_permissions(self):
        denied = self.client.get('/api/tools/')
        self.assertEqual(denied.status_code, 401)

        self.user_in_group('vue_member_tools', '正式成员')
        self.client.login(username='vue_member_tools', password='pass12345')
        response = self.client.get('/api/tools/')
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['tools'][0]['key'], 'bondreminder')

    def test_overview_api_requires_login_and_exposes_bond_reminder_summary(self):
        anonymous_response = self.client.get('/api/overview/')

        self.assertEqual(anonymous_response.status_code, 401)

        self.user_in_group('vue_member_overview', '正式成员')
        self.client.login(username='vue_member_overview', password='pass12345')
        member_response = self.client.get('/api/overview/')
        member_payload = json.loads(member_response.content)
        bond_reminder = member_payload['data']['bond_reminder']

        self.assertEqual(member_response.status_code, 200)
        self.assertTrue(bond_reminder['available'])
        self.assertIn('weekly_events', bond_reminder)
        self.assertIn('today_events', bond_reminder)
        self.assertIn('display_columns', bond_reminder)

    def test_overview_requires_login_even_if_anonymous_permission_is_enabled(self):
        FeatureAccess.objects.filter(
            feature__key='overview',
            role=FeatureAccess.ROLE_ANONYMOUS,
            action=FeatureAccess.ACTION_VIEW,
        ).update(allowed=True)

        page_response = self.client.get(reverse('dashboard:home'))
        api_response = self.client.get('/api/overview/')

        self.assertEqual(page_response.status_code, 302)
        self.assertIn('/accounts/login/', page_response['Location'])
        self.assertEqual(api_response.status_code, 401)

    def test_daily_check_reports_events_missing_contacts(self):
        today = datetime.now().date()
        with TemporaryDirectory() as temp_dir:
            table_path = f'{temp_dir}/bond.csv'
            with open(table_path, 'w', encoding='utf-8-sig') as table:
                table.write('证券代码,证券简称,2026年度付息日（T）,对接人姓名,对接人手机号\n')
                table.write(f'2320025.IB,23北京银行01,{today},,\n')
            save_bond_table_from_upload(table_path, source_name='daily-check.csv')

            reminder = BondReminder(
                {
                    'sender_email': 'sender@example.com',
                    'excel_path': str(BOND_CACHE_FILE),
                    'header_row_index': 0,
                    'date_columns': ['2026年度付息日（T）'],
                    'col_contact_name': '对接人姓名',
                    'col_contact_phone': '对接人手机号',
                    'daily_msg_template': '”{证券简称}“ {短信文本}',
                    'daily_msg_intro': '您好，今日有{n}项债券事项需要处理：',
                    'column_sms_texts': {'2026年度付息日（T）': '付息日'},
                }
            )

            logs = reminder.run_daily_check()

        self.assertTrue(any('今日检测到 1 条事项，但未生成每日提醒' in log for log in logs))
        self.assertTrue(any('缺少对接人姓名或手机号' in log for log in logs))

    def test_public_intern_link_is_read_only_and_only_sees_self(self):
        intern = Intern.objects.create(name='实习生甲')
        other = Intern.objects.create(name='实习生乙')
        InternSchedule.objects.create(
            intern=other,
            created_by=None,
            schedule_type=InternSchedule.TYPE_LEAVE,
            title='其他人请假',
            start_time=timezone.make_aware(datetime.fromisoformat(f'{self.schedule_day()}T09:00:00')),
            end_time=timezone.make_aware(datetime.fromisoformat(f'{self.schedule_day()}T10:00:00')),
        )

        schedules_response = self.client.get(f'/api/intern-share/{intern.access_token}/?week_start={self.schedule_day()}')
        schedules_payload = json.loads(schedules_response.content)

        self.assertEqual(schedules_response.status_code, 200)
        self.assertEqual(schedules_payload['data']['intern']['id'], intern.id)
        self.assertEqual(schedules_payload['data']['schedules'], [])
        self.assertFalse(schedules_payload['data']['capabilities']['can_request_leave'])

        denied_work = self.client.post(
            f'/api/intern-share/{intern.access_token}/',
            data=json.dumps(self.schedule_payload(intern)),
            content_type='application/json',
        )
        self.assertEqual(denied_work.status_code, 405)

        leave_payload = self.schedule_payload(intern, title='请假')
        leave_payload['schedule_type'] = InternSchedule.TYPE_LEAVE
        leave_response = self.client.post(
            f'/api/intern-share/{intern.access_token}/',
            data=json.dumps(leave_payload),
            content_type='application/json',
        )
        self.assertEqual(leave_response.status_code, 405)
        self.assertFalse(InternSchedule.objects.filter(intern=intern).exists())

    def test_public_intern_share_page_has_no_login_or_management_controls(self):
        intern = Intern.objects.create(name='纯展示实习生')

        response = self.client.get(f'/interns/share/{intern.access_token}/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '登录')
        self.assertNotContains(response, '实习生列表')
        self.assertContains(response, 'id="prevWeekBtn"')
        self.assertContains(response, 'id="currentWeekBtn"')
        self.assertContains(response, 'id="nextWeekBtn"')
        self.assertNotContains(response, 'id="leaveBtn"')
        self.assertNotContains(response, 'id="workBtn"')
        self.assertNotContains(response, 'id="internList"')

    def test_member_can_edit_intern_list(self):
        self.user_in_group('intern_list_member', '正式成员')
        self.client.login(username='intern_list_member', password='pass12345')

        create_response = self.client.post(
            '/api/interns/',
            data=json.dumps({'name': '新实习生', 'note': '暑期'}),
            content_type='application/json',
        )
        intern_id = json.loads(create_response.content)['data']['id']
        patch_response = self.client.patch(
            f'/api/interns/{intern_id}/',
            data=json.dumps({'name': '更新实习生', 'note': '长期'}),
            content_type='application/json',
        )
        delete_response = self.client.delete(f'/api/interns/{intern_id}/')

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(Intern.objects.get(id=intern_id).is_active)

    def test_intern_disable_button_lives_in_edit_modal(self):
        self.user_in_group('intern_disable_member', '正式成员')
        self.client.login(username='intern_disable_member', password='pass12345')

        response = self.client.get(reverse('dashboard:interns'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="deleteInternBtn"')
        self.assertContains(response, 'id="deleteInternInModalBtn"')
        self.assertContains(response, 'id="copyToast"')
        self.assertContains(response, 'position:relative;display:grid;width:100%;min-width:0')

    def test_leave_schedule_can_be_edited_by_any_member(self):
        intern = Intern.objects.create(name='请假对象')
        creator = self.user_in_group('leave_creator', '正式成员')
        editor = self.user_in_group('leave_editor', '正式成员')
        schedule = InternSchedule.objects.create(
            intern=intern,
            created_by=creator,
            schedule_type=InternSchedule.TYPE_LEAVE,
            title='请假',
            start_time=timezone.make_aware(datetime.fromisoformat(f'{self.schedule_day()}T14:00:00')),
            end_time=timezone.make_aware(datetime.fromisoformat(f'{self.schedule_day()}T15:00:00')),
        )
        self.client.login(username='leave_editor', password='pass12345')

        patch_response = self.client.patch(
            f'/api/intern-schedules/{schedule.id}/',
            data=json.dumps({'title': '协助调整请假'}),
            content_type='application/json',
        )

        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(InternSchedule.objects.get(id=schedule.id).title, '协助调整请假')

    def test_member_can_create_leave_for_intern(self):
        intern = Intern.objects.create(name='请假创建对象')
        self.user_in_group('leave_create_member', '正式成员')
        self.client.login(username='leave_create_member', password='pass12345')
        payload = self.schedule_payload(intern, start='14:00', end='15:00', title='请假')
        payload['schedule_type'] = InternSchedule.TYPE_LEAVE

        response = self.client.post(
            '/api/intern-schedules/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(InternSchedule.objects.get(intern=intern).schedule_type, InternSchedule.TYPE_LEAVE)

    def test_member_can_create_weekend_schedule_and_week_view_ends_on_sunday(self):
        intern = Intern.objects.create(name='周末安排对象')
        self.user_in_group('weekend_schedule_member', '正式成员')
        self.client.login(username='weekend_schedule_member', password='pass12345')
        saturday = self.weekend_day()
        payload = self.schedule_payload(intern, start='09:00', end='12:00', title='周末上午安排')
        payload['start_time'] = f'{saturday}T09:00:00'
        payload['end_time'] = f'{saturday}T12:00:00'

        create_response = self.client.post(
            '/api/intern-schedules/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        list_response = self.client.get(f'/api/intern-schedules/?intern_id={intern.id}&week_start={self.schedule_day()}')
        list_payload = json.loads(list_response.content)['data']

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_payload['week_end'], (datetime.fromisoformat(self.schedule_day()).date() + timedelta(days=6)).isoformat())
        self.assertEqual(list_payload['schedules'][0]['title'], '周末上午安排')

    def test_member_creating_lunch_only_work_is_silently_ignored(self):
        intern = Intern.objects.create(name='午休安排对象')
        self.user_in_group('lunch_schedule_member', '正式成员')
        self.client.login(username='lunch_schedule_member', password='pass12345')

        response = self.client.post(
            '/api/intern-schedules/',
            data=json.dumps(self.schedule_payload(intern, start='12:00', end='13:30', title='午休安排')),
            content_type='application/json',
        )
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['data']['skipped'])
        self.assertFalse(InternSchedule.objects.filter(intern=intern).exists())

    def test_member_can_create_work_that_spans_lunch_break(self):
        intern = Intern.objects.create(name='跨午休工作对象')
        self.user_in_group('lunch_work_member', '正式成员')
        self.client.login(username='lunch_work_member', password='pass12345')
        payload = self.schedule_payload(intern, start='09:00', end='14:00', title='跨午休工作')

        response = self.client.post(
            '/api/intern-schedules/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        response_payload = json.loads(response.content)
        schedules = list(InternSchedule.objects.filter(intern=intern).order_by('start_time'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response_payload['ok'])
        self.assertEqual(len(schedules), 2)
        self.assertEqual([(timezone.localtime(item.start_time).strftime('%H:%M'), timezone.localtime(item.end_time).strftime('%H:%M')) for item in schedules], [('09:00', '12:00'), ('13:30', '14:00')])

    def test_member_can_create_leave_that_spans_lunch_break(self):
        intern = Intern.objects.create(name='跨午休请假对象')
        self.user_in_group('lunch_leave_member', '正式成员')
        self.client.login(username='lunch_leave_member', password='pass12345')
        payload = self.schedule_payload(intern, start='11:00', end='14:00', title='请假')
        payload['schedule_type'] = InternSchedule.TYPE_LEAVE

        response = self.client.post(
            '/api/intern-schedules/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        response_payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response_payload['ok'])
        schedules = list(InternSchedule.objects.filter(intern=intern).order_by('start_time'))
        self.assertEqual(len(schedules), 2)
        self.assertTrue(all(schedule.schedule_type == InternSchedule.TYPE_LEAVE for schedule in schedules))
        self.assertEqual([(timezone.localtime(item.start_time).strftime('%H:%M'), timezone.localtime(item.end_time).strftime('%H:%M')) for item in schedules], [('11:00', '12:00'), ('13:30', '14:00')])

    def test_lunch_only_leave_does_not_conflict_with_leave_spanning_lunch(self):
        intern = Intern.objects.create(name='午休请假冲突对象')
        member = self.user_in_group('lunch_leave_conflict_member', '正式成员')
        self.client.login(username='lunch_leave_conflict_member', password='pass12345')
        day = self.schedule_day()
        InternSchedule.objects.create(
            intern=intern,
            created_by=member,
            schedule_type=InternSchedule.TYPE_LEAVE,
            title='午休请假',
            start_time=timezone.make_aware(datetime.fromisoformat(f'{day}T12:00:00')),
            end_time=timezone.make_aware(datetime.fromisoformat(f'{day}T13:30:00')),
        )
        payload = self.schedule_payload(intern, start='11:00', end='14:00', title='跨午休请假')
        payload['schedule_type'] = InternSchedule.TYPE_LEAVE

        response = self.client.post(
            '/api/intern-schedules/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(InternSchedule.objects.filter(intern=intern).count(), 3)

    def test_member_can_create_but_not_edit_others_schedule_and_conflicts_are_rejected(self):
        intern = Intern.objects.create(name='成员安排对象')
        member = self.user_in_group('schedule_member', '正式成员', first_name='Schedule Owner')
        other_member = self.user_in_group('schedule_other_member', '正式成员')
        self.client.login(username='schedule_member', password='pass12345')

        create_response = self.client.post(
            '/api/intern-schedules/',
            data=json.dumps(self.schedule_payload(intern, start='09:30', end='10:30')),
            content_type='application/json',
        )
        self.assertEqual(create_response.status_code, 200)
        created_schedule = json.loads(create_response.content)['data']
        self.assertEqual(created_schedule['created_by_name'], 'Schedule Owner')
        schedule_id = created_schedule['id']

        conflict_response = self.client.post(
            '/api/intern-schedules/',
            data=json.dumps(self.schedule_payload(intern, start='10:00', end='11:00', title='冲突安排')),
            content_type='application/json',
        )
        self.assertEqual(conflict_response.status_code, 400)
        conflict_error = json.loads(conflict_response.content)['error']
        self.assertIn('该时间段已有安排', conflict_error)
        self.assertIn('整理材料', conflict_error)
        self.assertIn('09:30-10:30', conflict_error)
        self.assertIn('重叠时间', conflict_error)
        self.assertIn('10:00-10:30', conflict_error)

        self.client.logout()
        self.client.login(username='schedule_other_member', password='pass12345')
        patch_response = self.client.patch(
            f'/api/intern-schedules/{schedule_id}/',
            data=json.dumps({'title': '别人修改'}),
            content_type='application/json',
        )
        delete_response = self.client.delete(f'/api/intern-schedules/{schedule_id}/')
        self.assertEqual(patch_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

        self.client.logout()
        self.client.login(username='schedule_member', password='pass12345')
        own_patch = self.client.patch(
            f'/api/intern-schedules/{schedule_id}/',
            data=json.dumps({'title': '自己修改'}),
            content_type='application/json',
        )
        self.assertEqual(own_patch.status_code, 200)
        self.assertEqual(InternSchedule.objects.get(id=schedule_id).title, '自己修改')

    def test_team_lead_can_manage_all_intern_schedules(self):
        intern = Intern.objects.create(name='负责人安排对象')
        member = self.user_in_group('lead_schedule_member', '正式成员')
        lead = self.user_in_group('schedule_lead', '团队负责人')
        schedule = InternSchedule.objects.create(
            intern=intern,
            created_by=member,
            schedule_type=InternSchedule.TYPE_WORK,
            title='成员安排',
            start_time=timezone.make_aware(datetime.fromisoformat(f'{self.schedule_day()}T11:00:00')),
            end_time=timezone.make_aware(datetime.fromisoformat(f'{self.schedule_day()}T12:00:00')),
        )
        self.client.login(username='schedule_lead', password='pass12345')

        patch_response = self.client.patch(
            f'/api/intern-schedules/{schedule.id}/',
            data=json.dumps({'title': '负责人修改'}),
            content_type='application/json',
        )
        delete_response = self.client.delete(f'/api/intern-schedules/{schedule.id}/')

        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(InternSchedule.objects.filter(id=schedule.id).exists())
