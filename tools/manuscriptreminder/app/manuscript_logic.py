import json
import re
from datetime import datetime, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

from tools.bondreminder.app.mailer import send_mail

from .logging_utils import append_log
from .storage import has_table, load_table_rows


class ManuscriptReminder:
    def __init__(self, config):
        self.config = config
        self.logs = []
        self.default_colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12", "#1abc9c"]

    def log(self, message):
        line = append_log(message)
        self.logs.append(line)

    def unique_receivers(self, receivers):
        result = []
        seen = set()
        for receiver in receivers:
            email = str(receiver or "").strip()
            key = email.lower()
            if email and key not in seen:
                result.append(email)
                seen.add(key)
        return result

    def get_week_range(self):
        today = datetime.now().date()
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)

    def get_this_friday(self):
        start, _ = self.get_week_range()
        return start + timedelta(days=4)

    def _parse_date(self, value):
        if value is None or str(value).strip() in {"", "-", "nan", "None"}:
            return None
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()

    def _business_days_between(self, start_date, end_date):
        if end_date < start_date:
            return -1
        days = 0
        current = start_date
        while current < end_date:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def _filtered_rows(self):
        if not has_table():
            return []
        owner_column = self.config.get("owner_column", "项目负责人")
        owner_name = str(self.config.get("owner_name", "潘学超")).strip()
        rows = []
        for item in load_table_rows():
            data = item.get("data") or {}
            if owner_name and str(data.get(owner_column, "")).strip() != owner_name:
                continue
            rows.append(item)
        return rows

    def _display_data(self, data, display_columns):
        date_columns = set(self.config.get("date_columns", []))
        date_columns.add(self.config.get("archive_deadline_column", "归档流程发起截止日"))
        date_columns.add(self.config.get("association_deadline_column", "协会报送截止日"))
        display_data = {}
        for column in display_columns:
            if column not in data:
                continue
            if column in date_columns:
                parsed = self._parse_date(data.get(column))
                if parsed:
                    display_data[column] = str(parsed)
                    continue
            display_data[column] = str(data.get(column, "") or "")
        return display_data

    def collect_overview(self, start_date=None, end_date=None):
        display_columns = [col for col in self.config.get("display_columns", [])]
        if not has_table():
            return {
                "available": True,
                "configured": False,
                "display_columns": display_columns,
                "archive_events": [],
                "overdue_events": [],
                "association_warning_events": [],
                "other_rows": [],
            }
        if start_date is None or end_date is None:
            start_date, end_date = self.get_week_range()
        friday = self.get_this_friday()
        archive_column = self.config.get("archive_deadline_column", "归档流程发起截止日")
        association_column = self.config.get("association_deadline_column", "协会报送截止日")
        threshold = int(self.config.get("association_workday_threshold") or 10)
        colors = self.config.get("column_colors", {})
        rows = self._filtered_rows()
        if not rows:
            return {
                "available": True,
                "configured": False,
                "owner_name": self.config.get("owner_name", "潘学超"),
                "week_range": {
                    "start": str(start_date),
                    "end": str(end_date),
                    "label": f"{start_date.strftime('%m.%d')} - {end_date.strftime('%m.%d')}",
                },
                "friday": str(friday),
                "threshold": threshold,
                "display_columns": display_columns,
                "archive_events": [],
                "overdue_events": [],
                "association_warning_events": [],
                "other_rows": [],
                "archive_count": 0,
                "overdue_count": 0,
                "association_warning_count": 0,
                "other_count": 0,
            }

        overdue_events = []
        association_warning_events = []
        summary_events_by_row = {}
        seen_summary_rows = set()
        row_display_items = []

        def summary_for(item, base_event):
            key = str(base_event.get("source_row") or item.get("row_index"))
            if key not in summary_events_by_row:
                summary_events_by_row[key] = {
                    **base_event,
                    "date_str": "",
                    "weekday": "",
                    "event_type": "",
                    "event_types": [],
                    "color": self.default_colors[0],
                    "sort_date": "9999-12-31",
                }
            seen_summary_rows.add(key)
            return summary_events_by_row[key]

        def add_summary_type(item, base_event, event_type, color, date_value=None, weekday=""):
            summary = summary_for(item, base_event)
            if not any(existing.get("label") == event_type for existing in summary["event_types"]):
                summary["event_types"].append({"label": event_type, "color": color})
            summary["event_type"] = "、".join(event["label"] for event in summary["event_types"])
            if date_value and not summary["date_str"]:
                summary["date_str"] = str(date_value)
                summary["weekday"] = weekday
                summary["sort_date"] = str(date_value)
            return summary

        for item in rows:
            data = item.get("data") or {}
            style = item.get("style") or {}
            archive_date = self._parse_date(data.get(archive_column))
            association_date = self._parse_date(data.get(association_column))
            base_event = {
                "display_data": self._display_data(data, display_columns),
                "source_row": style.get("excel_row") or item.get("row_index"),
            }
            row_display_items.append(base_event)

            if archive_date and start_date <= archive_date <= end_date:
                add_summary_type(
                    item,
                    base_event,
                    archive_column,
                    colors.get(archive_column, self.default_colors[0]),
                    archive_date,
                    ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][archive_date.weekday()],
                )

            if style.get("fill_alert") in {"yellow", "red"}:
                overdue_color = "#e74c3c" if style.get("fill_alert") == "red" else "#f1c40f"
                overdue_event = {
                    **base_event,
                    "date_str": str(association_date or archive_date or ""),
                    "event_type": "逾期提醒",
                    "alert_level": style.get("fill_alert"),
                    "color": overdue_color,
                }
                overdue_events.append(overdue_event)
                add_summary_type(item, base_event, "逾期提醒", overdue_color)

            if association_date:
                remaining = self._business_days_between(friday, association_date)
                if 0 <= remaining < threshold:
                    association_color = colors.get(association_column, self.default_colors[4])
                    association_label = f"本周五距离截止日{remaining}工作日"
                    association_event = {
                        **base_event,
                        "date_str": str(association_date),
                        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][association_date.weekday()],
                        "event_type": association_label,
                        "remaining_workdays": remaining,
                        "color": association_color,
                    }
                    association_warning_events.append(association_event)
                    add_summary_type(item, base_event, association_label, association_color)

        archive_events = list(summary_events_by_row.values())
        archive_events.sort(key=lambda item: (item["sort_date"], item["source_row"]))
        overdue_events.sort(key=lambda item: (item["alert_level"], item["date_str"]))
        association_warning_events.sort(key=lambda item: (item["remaining_workdays"], item["date_str"]))
        other_rows = [
            {
                **item,
                "date_str": "",
                "weekday": "",
                "event_type": "无需提醒",
                "event_types": [],
                "color": "#94a3b8",
            }
            for item in row_display_items
            if str(item.get("source_row")) not in seen_summary_rows
        ]
        other_rows.sort(key=lambda item: item["source_row"])
        return {
            "available": True,
            "configured": True,
            "owner_name": self.config.get("owner_name", "潘学超"),
            "week_range": {
                "start": str(start_date),
                "end": str(end_date),
                "label": f"{start_date.strftime('%m.%d')} - {end_date.strftime('%m.%d')}",
            },
            "friday": str(friday),
            "threshold": threshold,
            "display_columns": display_columns,
            "archive_events": archive_events,
            "overdue_events": overdue_events,
            "association_warning_events": association_warning_events,
            "other_rows": other_rows,
            "archive_count": len(archive_events),
            "overdue_count": len(overdue_events),
            "association_warning_count": len(association_warning_events),
            "other_count": len(other_rows),
        }

    def run_weekly_check(self):
        self.logs = []
        self.log(">>> 开始执行【底稿报送周报】任务...")
        overview = self.collect_overview()
        events = {
            "archive": overview["archive_events"],
            "overdue": overview["overdue_events"],
            "association": overview["association_warning_events"],
        }
        self.send_email_report(overview, events)
        if not any(events.values()):
            self.log("本周无底稿报送提醒事项。")
        return self.logs

    def send_email_report(self, overview, events):
        sender = self.config.get("sender_email")
        password = self.config.get("auth_code")
        receivers = self.unique_receivers(item.get("email", "") for item in self.config.get("receiver_list", []))
        if not sender or not password:
            self.log("错误: 未配置发件人邮箱或授权码。")
            return
        if not receivers:
            self.log("错误: 收件人列表为空。")
            return
        subject = f"{self.config.get('email_subject', '底稿报送提醒')} ({overview.get('week_range', {}).get('label', '')})"
        intro = self.config.get("email_intro", "底稿报送提醒事项如下：")
        html = self._build_email_html(subject, intro, overview, events)
        msg = MIMEMultipart()
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender
        msg["To"] = ",".join(receivers)
        msg.attach(MIMEText(html, "html", "utf-8"))
        try:
            result = send_mail(sender, password, receivers, msg)
            self.log(f"底稿报送周报发送成功（收件人 {len(receivers)} 个，SMTP {result['mode']}:{result['port']}）")
        except Exception as exc:
            self.log(f"底稿报送周报发送失败: {exc}")

    def _build_email_html(self, subject, intro, overview, grouped_events):
        display_columns = overview.get("display_columns", [])
        sections = [
            ("本周需要提归档流程", grouped_events.get("archive", [])),
        ]
        html = f"""
        <html><head><style>
        body {{ font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; color: #333; }}
        .container {{ width: 95%; max-width: 1100px; margin: 0 auto; }}
        .header {{ background: #2c3e50; color: #fff; padding: 15px; border-radius: 6px 6px 0 0; }}
        .intro {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #3498db; margin: 15px 0; }}
        table {{ width: 100%; border-collapse: collapse; border: 1px solid #ddd; margin: 10px 0 22px; }}
        th {{ background: #eee; padding: 8px; border: 1px solid #ddd; text-align: left; white-space: nowrap; }}
        td {{ padding: 7px 8px; border: 1px solid #ddd; }}
        .tag {{ display:inline-block; padding:3px 7px; border-radius:4px; color:#fff; font-weight:bold; font-size:12px; }}
        </style></head><body><div class="container">
        <div class="header"><h2>{subject}</h2></div>
        <div class="intro"><p>{intro}</p><p>负责人：{overview.get('owner_name', '')}；本周范围：{overview.get('week_range', {}).get('label', '')}</p></div>
        """
        for title, events in sections:
            html += f"<h3>{title}（{len(events)}）</h3>"
            if not events:
                html += "<p>暂无事项。</p>"
                continue
            html += "<table><thead><tr><th>提醒类型</th><th>日期/剩余工作日</th>"
            for column in display_columns:
                html += f"<th>{column}</th>"
            html += "</tr></thead><tbody>"
            for event in events:
                first = event.get("date_str", "")
                if "remaining_workdays" in event:
                    first = f"{first}（剩余 {event['remaining_workdays']} 工作日）"
                tags = event.get("event_types") or [{"label": event.get("event_type", ""), "color": event.get("color", "#3498db")}]
                tag_html = "".join(
                    f"<span class='tag' style='background:{tag.get('color', '#3498db')}'>{tag.get('label', '')}</span> "
                    for tag in tags
                )
                html += f"<tr><td>{tag_html}</td><td>{first}</td>"
                for column in display_columns:
                    html += f"<td>{event.get('display_data', {}).get(column, '')}</td>"
                html += "</tr>"
            html += "</tbody></table>"
        html += "<p style='text-align:center;color:#999;font-size:12px;'>Powered by ManuscriptReminder</p></div></body></html>"
        return html

    def run_daily_check(self):
        self.logs = []
        self.log(">>> 开始执行【底稿报送每日短信】任务...")
        sender = self.config.get("sender_email")
        if not sender:
            self.log("错误: 未配置发件人邮箱，无法发送每日提醒。")
            return self.logs
        today = datetime.now().date()
        texts = self.config.get("column_sms_texts", {})
        msg_template = self.config.get("daily_msg_template", "“{项目名称}” {短信文本}")
        intro = self.config.get("daily_msg_intro", "您好，今日有{n}项底稿报送事项需要处理：")
        today_events = []
        for item in self._filtered_rows():
            data = item.get("data") or {}
            for column in self.config.get("date_columns", []):
                event_date = self._parse_date(data.get(column))
                if event_date != today:
                    continue
                text = msg_template.replace("{短信文本}", texts.get(column, column)).replace("{事件类型}", texts.get(column, column))
                for placeholder in re.findall(r"\{(.+?)\}", text):
                    if placeholder in data:
                        text = text.replace(f"{{{placeholder}}}", str(data.get(placeholder, "") or ""))
                today_events.append(text)
        if not today_events:
            self.log("今日无底稿报送事项，不发送每日提醒。")
            return self.logs
        daily_receiver = self.config.get("daily_email_receiver", "").strip() or sender
        message = intro.replace("{n}", str(len(today_events))) + "\n" + "\n".join(
            f"{index + 1}.{text}" for index, text in enumerate(today_events)
        )
        msg = MIMEText(json.dumps({"message": message, "name": self.config.get("owner_name", ""), "phone": ""}, ensure_ascii=False), "plain", "utf-8")
        msg["Subject"] = Header("BondTrigger", "utf-8")
        msg["From"] = sender
        msg["To"] = daily_receiver
        try:
            result = send_mail(sender, self.config.get("auth_code"), [daily_receiver], msg)
            self.log(f"每日短信提醒触发邮件已发送（共 {len(today_events)} 条，SMTP {result['mode']}:{result['port']}）")
        except Exception as exc:
            self.log(f"每日短信提醒发送失败: {exc}")
        return self.logs
