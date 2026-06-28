import json
import re
from datetime import datetime, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

from .logging_utils import append_log
from .mailer import send_mail
from .storage import has_bond_table, read_table


class BondReminder:
    def __init__(self, config):
        self.config = config
        self.logs = []
        self.default_colors = [
            "#e74c3c",
            "#3498db",
            "#2ecc71",
            "#9b59b6",
            "#f39c12",
            "#1abc9c",
            "#d35400",
        ]

    def log(self, message):
        full_msg = append_log(message)
        self.logs.append(full_msg)

    def get_week_range(self):
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return start_of_week, end_of_week

    def _read_excel(self, log_errors=True):
        excel_path = self.config.get("excel_path")
        header_idx = self.config.get("header_row_index", 0)
        if not excel_path or not has_bond_table():
            if log_errors:
                self.log("错误: 数据库中尚无债券数据。请先上传数据。")
            return None
        try:
            return read_table(excel_path, header=header_idx)
        except Exception as exc:
            if log_errors:
                self.log(f"读取数据文件失败: {exc}")
            return None

    def collect_events(self, start_date=None, end_date=None):
        """Return reminder events without sending email or writing logs."""
        target_cols = self.config.get("date_columns", [])
        display_cols = self.config.get("display_columns", [])
        if not target_cols:
            return {"events": [], "display_columns": display_cols, "configured": False}

        df = self._read_excel(log_errors=False)
        if df is None:
            return {"events": [], "display_columns": display_cols, "configured": False}

        if start_date is None or end_date is None:
            start_date, end_date = self.get_week_range()

        valid_date_cols = [col for col in target_cols if col in df.columns]
        valid_display_cols = [col for col in display_cols if col in df.columns]
        if not valid_date_cols:
            return {"events": [], "display_columns": valid_display_cols, "configured": False}

        user_colors = self.config.get("column_colors", {})
        events = []
        for _, row in df.iterrows():
            for date_col in valid_date_cols:
                raw_date = row[date_col]
                if pd.isna(raw_date) or str(raw_date).strip() in ["-", "", "nan"]:
                    continue
                dt = pd.to_datetime(raw_date, errors="coerce")
                if pd.isna(dt):
                    continue
                event_date = dt.date()
                if start_date <= event_date <= end_date:
                    row_data = {}
                    for display_col in valid_display_cols:
                        val = row[display_col]
                        row_data[display_col] = str(val) if not pd.isna(val) else ""
                    events.append(
                        {
                            "date_str": str(event_date),
                            "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][event_date.weekday()],
                            "event_type": date_col,
                            "color": user_colors.get(
                                date_col,
                                self.default_colors[valid_date_cols.index(date_col) % len(self.default_colors)],
                            ),
                            "display_data": row_data,
                        }
                    )

        events.sort(key=lambda item: (item["date_str"], item["event_type"]))
        return {"events": events, "display_columns": valid_display_cols, "configured": True}

    def run_weekly_check(self):
        self.logs = []
        self.log(">>> 开始执行【每周报表】任务...")
        self.check_auth_expiry()

        target_cols = self.config.get("date_columns", [])
        display_cols = self.config.get("display_columns", [])
        if not target_cols:
            self.log("警告: 未配置监控列，无法筛选日期。")
            return self.logs

        df = self._read_excel()
        if df is None:
            return self.logs

        try:
            start_date, end_date = self.get_week_range()
            self.log(f"周报扫描范围: {start_date} ~ {end_date}")
            valid_date_cols = [col for col in target_cols if col in df.columns]
            if not valid_date_cols:
                self.log("错误: 选中的监控列在表格中都找不到。")
                return self.logs

            events_found = []
            for _, row in df.iterrows():
                for date_col in valid_date_cols:
                    raw_date = row[date_col]
                    if pd.isna(raw_date) or str(raw_date).strip() in ["-", "", "nan"]:
                        continue
                    dt = pd.to_datetime(raw_date, errors="coerce")
                    if pd.isna(dt):
                        continue
                    event_date = dt.date()
                    if start_date <= event_date <= end_date:
                        row_data = {}
                        for display_col in display_cols:
                            if display_col in df.columns:
                                val = row[display_col]
                                row_data[display_col] = str(val) if not pd.isna(val) else ""
                        events_found.append(
                            {
                                "date_obj": event_date,
                                "date_str": str(event_date),
                                "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][
                                    event_date.weekday()
                                ],
                                "event_type": date_col,
                                "display_data": row_data,
                            }
                        )

            events_found.sort(key=lambda item: (item["event_type"], item["date_obj"]))
            self.send_email_report(events_found, start_date, end_date, display_cols)
            if not events_found:
                self.log("本周无相关事项，已发送空事件提醒邮件。")
        except Exception as exc:
            self.log(f"周报执行出错: {exc}")
        return self.logs

    def send_email_report(self, events, start_date, end_date, display_cols):
        sender = self.config.get("sender_email")
        password = self.config.get("auth_code")
        receiver_list_cfg = self.config.get("receiver_list", [])
        receivers = [item.get("email", "").strip() for item in receiver_list_cfg if item.get("email", "").strip()]

        if not sender or not password:
            self.log("错误: 未配置发件人邮箱或授权码。")
            return
        if not receivers:
            self.log("错误: 收件人列表为空，取消发送。")
            return

        subject_tmpl = self.config.get("email_subject", "债券提醒周报")
        subject = f"{subject_tmpl} ({start_date.strftime('%m.%d')}-{end_date.strftime('%m.%d')})"

        if not events:
            html = f"""
            <html><head><style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; color: #333; }}
            .container {{ width: 95%; max-width: 1000px; margin: 0 auto; }}
            .header {{ background: #2c3e50; color: #fff; padding: 15px; border-radius: 6px 6px 0 0; }}
            .intro {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #3498db; margin: 15px 0; }}
            .no-events {{ text-align: center; padding: 40px 0; color: #666; font-size: 16px; }}
            </style></head><body><div class="container">
            <div class="header"><h2>{subject}</h2></div>
            <div class="intro"><p>统计范围：{start_date} 至 {end_date}</p></div>
            <div class="no-events"><p><strong>本周无事件</strong></p></div>
            <p style="text-align:center; color:#999; margin-top:20px; font-size:12px;">Powered by BondReminder</p>
            </div></body></html>
            """
        else:
            intro_text = self.config.get("email_intro", "本周提醒事项如下：")
            user_colors = self.config.get("column_colors", {})
            table_headers = """
                <th width="15%">事件类型</th>
                <th width="15%">日期</th>
                <th width="8%">星期</th>
            """
            for col in display_cols:
                table_headers += f"<th>{col}</th>"

            html = f"""
            <html><head><style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; color: #333; }}
            .container {{ width: 95%; max-width: 1000px; margin: 0 auto; }}
            .header {{ background: #2c3e50; color: #fff; padding: 15px; border-radius: 6px 6px 0 0; }}
            .intro {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #3498db; margin: 15px 0; }}
            table {{ width: 100%; border-collapse: collapse; border: 1px solid #ddd; margin-top: 10px; }}
            th {{ background: #eee; padding: 10px; border: 1px solid #ddd; text-align: left; white-space: nowrap; }}
            td {{ padding: 8px 10px; border: 1px solid #ddd; }}
            .tag {{ display: inline-block; padding: 4px 8px; border-radius: 4px; color: #fff; font-size: 12px; font-weight: bold; min-width: 60px; text-align: center; }}
            .date-highlight {{ font-weight: bold; color: #e74c3c; }}
            </style></head><body><div class="container">
            <div class="header"><h2>{subject}</h2></div>
            <div class="intro"><p>{intro_text}</p><p>统计范围：{start_date} 至 {end_date}，共发现 <strong>{len(events)}</strong> 条事项。</p></div>
            <table><thead><tr>{table_headers}</tr></thead><tbody>
            """
            for event in events:
                event_name = event["event_type"]
                bg_color = user_colors.get(event_name, self.default_colors[hash(event_name) % len(self.default_colors)])
                html += f"""
                <tr><td><span class="tag" style="background-color: {bg_color}">{event_name}</span></td>
                <td class="date-highlight">{event['date_str']}</td><td>{event['weekday']}</td>
                """
                for col in display_cols:
                    html += f"<td>{event['display_data'].get(col, '')}</td>"
                html += "</tr>"
            html += "</tbody></table><p style='text-align:center; color:#999; margin-top:20px; font-size:12px;'>Powered by BondReminder</p></div></body></html>"

        msg = MIMEMultipart()
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender
        msg["To"] = ",".join(receivers)
        msg.attach(MIMEText(html, "html", "utf-8"))
        try:
            result = send_mail(sender, password, receivers, msg)
            self.log(f"周报发送成功（收件人 {len(receivers)} 个，SMTP {result['mode']}:{result['port']}）")
        except Exception as exc:
            self.log(f"周报发送失败: {exc}")

    def run_daily_check(self):
        self.logs = []
        self.log(">>> 开始执行【每日自查】任务...")
        sender = self.config.get("sender_email")
        if not sender:
            self.log("错误: 未配置发件人邮箱，无法发送每日提醒。")
            return self.logs

        col_name = self.config.get("col_contact_name", "").strip()
        col_phone = self.config.get("col_contact_phone", "").strip()
        msg_template = self.config.get("daily_msg_template", "").strip() or "”{证券简称}“ {短信文本}"
        sms_texts = self.config.get("column_sms_texts", {})
        intro_template = self.config.get("daily_msg_intro", "您好，今日有{n}项债券事项需要处理：")
        if not col_name or not col_phone:
            self.log("警告: 未配置【对接人姓名】或【手机号】列，日报内容可能不完整。")

        df = self._read_excel()
        if df is None:
            return self.logs
        target_cols = self.config.get("date_columns", [])
        if not target_cols:
            self.log("警告: 未配置监控日期列。")
            return self.logs

        today = datetime.now().date()
        self.log(f"扫描今日事件: {today}")
        grouped_events = {}
        today_event_count = 0
        missing_contact_count = 0
        contact_columns_missing = [col for col in [col_name, col_phone] if col and col not in df.columns]
        if contact_columns_missing:
            self.log(f"警告: 表格中找不到联系人列：{', '.join(contact_columns_missing)}。")

        for _, row in df.iterrows():
            for date_col in target_cols:
                if date_col not in df.columns:
                    continue
                raw_date = row[date_col]
                if pd.isna(raw_date) or str(raw_date).strip() in ["-", "", "nan"]:
                    continue
                dt = pd.to_datetime(raw_date, errors="coerce")
                if pd.isna(dt) or dt.date() != today:
                    continue

                today_event_count += 1
                name_val = str(row[col_name]) if col_name and col_name in df.columns and not pd.isna(row[col_name]) else "未知"
                phone_val = str(row[col_phone]) if col_phone and col_phone in df.columns and not pd.isna(row[col_phone]) else ""
                names = [name.strip() for name in name_val.split("&") if name.strip()]
                phones = [phone.strip() for phone in phone_val.split("&") if phone.strip()]
                min_len = min(len(names), len(phones))
                if min_len == 0:
                    missing_contact_count += 1
                    continue

                display_text = sms_texts.get(date_col) or date_col
                current_template = msg_template.replace("{短信文本}", display_text).replace("{事件类型}", display_text)
                formatted_event = current_template
                for placeholder in re.findall(r"\{(.+?)\}", current_template):
                    if placeholder in df.columns:
                        val = str(row[placeholder]) if not pd.isna(row[placeholder]) else ""
                        formatted_event = formatted_event.replace(f"{{{placeholder}}}", val)

                for index in range(min_len):
                    current_phone = phones[index]
                    if current_phone.endswith(".0"):
                        current_phone = current_phone[:-2]
                    current_phone = current_phone.strip()
                    if not current_phone:
                        continue
                    grouped_events.setdefault(current_phone, {"name": names[index] if index < len(names) else "未知", "events": []})
                    grouped_events[current_phone]["events"].append(formatted_event)

        daily_events_list = []
        for phone, data in grouped_events.items():
            header = intro_template.replace("{n}", str(len(data["events"])))
            message = header + "\n" + "\n".join(f"{idx + 1}.{text}" for idx, text in enumerate(data["events"]))
            daily_events_list.append({"message": message.rstrip(), "name": data["name"], "phone": phone})

        if daily_events_list:
            if missing_contact_count:
                self.log(f"今日检测到 {today_event_count} 条事项，其中 {missing_contact_count} 条缺少对接人姓名或手机号，已跳过。")
            self.send_daily_email(daily_events_list)
        else:
            if today_event_count:
                self.log(
                    f"今日检测到 {today_event_count} 条事项，但未生成每日提醒："
                    f"{missing_contact_count or today_event_count} 条缺少对接人姓名或手机号。"
                    f"请检查表格列【{col_name or '未配置'}】和【{col_phone or '未配置'}】。"
                )
            else:
                self.log("今日无事项，不发送每日提醒。")
        return self.logs

    def send_daily_email(self, events_list):
        sender = self.config.get("sender_email")
        password = self.config.get("auth_code")
        if not sender or not password:
            self.log("错误: 未配置发件人邮箱或授权码。")
            return
        subject = "BondTrigger"
        daily_receiver = self.config.get("daily_email_receiver", "").strip() or sender
        email_body = "&".join(json.dumps(event, ensure_ascii=False) for event in events_list)
        msg = MIMEText(email_body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender
        msg["To"] = daily_receiver
        try:
            result = send_mail(sender, password, [daily_receiver], msg)
            self.log(f"每日提醒已发送（JSON格式，共 {len(events_list)} 条，发给: {daily_receiver}，SMTP {result['mode']}:{result['port']}）")
        except Exception as exc:
            self.log(f"每日提醒发送失败: {exc}")

    def send_custom_email(self, task):
        sender = self.config.get("sender_email")
        password = self.config.get("auth_code")
        if not sender or not password:
            self.log("错误: 未配置发件人邮箱或授权码")
            return
        task_name = task.get("name", "未命名任务")
        subject = task.get("subject") or (
            f"BondTrigger自定义任务通知: {task_name}" if task.get("send_type") == "sms" else f"自定义任务：{task_name}"
        )
        body = task.get("content") or f"任务通知: {task_name}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        receivers = task.get("receivers", [])
        if not receivers:
            self.log("错误: 收件人列表为空")
            return
        msg = MIMEMultipart()
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender
        msg["To"] = ",".join(receivers)
        msg.attach(MIMEText(body, "plain", "utf-8"))
        try:
            result = send_mail(sender, password, receivers, msg)
            self.log(f"邮件投递成功（标题: {subject}，SMTP {result['mode']}:{result['port']}）")
        except Exception as exc:
            self.log(f"邮件发送失败: {exc}")

    def run_custom_task(self, task):
        self.log(f"--- 开始执行自定义任务: {task.get('name', '未命名任务')} ---")
        send_type = task.get("send_type")
        if send_type == "email":
            self.send_custom_email(task)
        elif send_type == "sms":
            target_email = self.config.get("daily_email_receiver")
            if not target_email:
                self.log("SMS发送失败: 请先配置短信中转邮箱")
            else:
                raw_content = task.get("content", "")
                content_lines = []
                for phone in task.get("receivers", []):
                    phone = str(phone).strip()
                    if phone:
                        content_lines.append(json.dumps({"message": raw_content, "phone": phone, "name": task.get("name", "自定义任务")}, ensure_ascii=False))
                proxy_task = task.copy()
                proxy_task["receivers"] = [target_email]
                proxy_task["content"] = "&".join(content_lines)
                proxy_task["subject"] = f"BondTrigger自定义任务通知: {task.get('name', '未命名任务')}"
                self.send_custom_email(proxy_task)
                self.log("SMS触发邮件已发送")
        else:
            self.log(f"任务类型 {send_type} 暂不支持")
        self.log(f"--- 自定义任务结束: {task.get('name', '未命名任务')} ---")

    def check_auth_expiry(self):
        if not self.config.get("auth_expiry_enabled", False):
            return
        try:
            start_str = self.config.get("auth_start_date")
            validity = int(self.config.get("auth_validity_days", 180))
            if not start_str:
                return
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            expiry_date = start_date + timedelta(days=validity)
            remaining_days = (expiry_date - datetime.now().date()).days
            if 0 <= remaining_days <= 10:
                self.log(f"【警报】授权码即将在 {remaining_days} 天后过期。")
                self.send_self_alert(remaining_days, expiry_date)
        except Exception as exc:
            self.log(f"检查授权码过期状态时出错: {exc}")

    def send_self_alert(self, remaining_days, expiry_date):
        sender = self.config.get("sender_email")
        password = self.config.get("auth_code")
        if not sender or not password:
            return
        subject = f"【紧急续期】您的邮箱授权码还有 {remaining_days} 天过期！"
        html_content = f"<p>授权码将于 {expiry_date} 过期，请及时更新。</p>"
        msg = MIMEMultipart()
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender
        msg["To"] = sender
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        try:
            send_mail(sender, password, [sender], msg)
        except Exception:
            pass
