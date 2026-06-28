import base64
import io
import json
import mimetypes
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path

from .logging_utils import append_log
from .mailer import send_mail
from .storage import load_config, load_customer_data, load_customer_settings, save_customer_data, save_customer_settings


def birthday_from_id(id_no):
    match = re.search(r"\d{6}(\d{4})(\d{2})(\d{2})", str(id_no))
    if not match:
        return ""
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def extract_response_text(data):
    texts = []

    def walk(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("text"), str):
                texts.append(obj["text"])
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return "\n".join(texts)


def _load_pillow():
    try:
        from PIL import Image, ImageOps
    except Exception as exc:
        raise RuntimeError("服务器缺少 Pillow，无法规范化图片。请执行 pip install -r requirements.txt 后重试。") from exc
    return Image, ImageOps


def _normalize_image_bytes(raw, source_name="图片"):
    Image, ImageOps = _load_pillow()
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in {"RGBA", "LA"}:
                background = Image.new("RGB", image.size, "white")
                alpha = image.getchannel("A")
                background.paste(image.convert("RGBA"), mask=alpha)
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
            max_side = 2200
            if max(image.size) > max_side:
                image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
    except Exception as exc:
        raise RuntimeError(f"{source_name}无法解析，请确认上传的是有效的 JPG、PNG、BMP、WebP 或 PDF 文件。") from exc


def _prepare_identity_payload(raw, fallback_mime):
    if raw.startswith(b"%PDF"):
        return "application/pdf", "input_file", "file_data", raw
    return "image/jpeg", "input_image", "image_url", _normalize_image_bytes(raw, fallback_mime or "图片")


def _format_identity_error(text):
    try:
        data = json.loads(text)
    except Exception:
        return text
    err = data.get("error") if isinstance(data, dict) else None
    if not isinstance(err, dict):
        return text
    code = err.get("code", "")
    message = err.get("message", "")
    if code == "InvalidParameter" and "base64" in message and ("image_url" in message or "file_url" in message):
        return "文件 base64 数据格式未被识别。请确认上传的是有效 JPG/PNG/PDF；如 PDF 仍失败，请尝试将身份证页另存为 JPG/PNG 后上传。"
    if code == "AccountOverdueError":
        return "API 账号欠费或余额逾期，请先检查火山引擎账户余额。"
    if "Error while connecting:" in message or "Error while connecting:" in text:
        return "接口把文件内容当作 URL 去访问了。PDF base64 必须使用 file_data 字段并携带 filename，请刷新后重试。"
    return message or text


def call_identity_ai(path, settings):
    if not settings.get("api_key"):
        raise RuntimeError("缺少 API Key")
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        raw = f.read()
    mime, content_type, url_key, payload_bytes = _prepare_identity_payload(raw, mime)
    encoded = base64.b64encode(payload_bytes).decode("ascii")
    try:
        base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError("文件 base64 编码校验失败，请重新上传文件。") from exc
    prompt = "请识别身份证中的姓名、身份证号和生日，只返回JSON，字段为：姓名、身份证号、生日。生日格式yyyy-MM-dd。"
    if content_type == "input_file":
        content_values = [f"data:{mime};base64,{encoded}"]
    else:
        content_values = [f"data:{mime};base64,{encoded}", encoded]
    raw = ""
    last_error = ""
    for content_value in content_values:
        if content_type == "input_file":
            content_item = {
                "type": content_type,
                "file_data": content_value,
                "filename": Path(path).name or "identity.pdf",
            }
        else:
            content_item = {"type": content_type, url_key: content_value}
            content_item["detail"] = "auto"
        payload = {
            "model": settings["model"],
            "input": [
                {
                    "role": "user",
                    "content": [
                        content_item,
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
        }
        req = urllib.request.Request(
            settings["api_url"],
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings['api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="ignore") or str(exc)
            last_error = _format_identity_error(text)
            if "base64" not in text or content_value == content_values[-1]:
                raise RuntimeError(last_error) from exc
    if not raw:
        raise RuntimeError(last_error or "身份证识别接口未返回内容。")
    data = json.loads(raw)
    text = extract_response_text(data)
    match = re.search(r"\{.*\}", text, re.S)
    return json.loads(match.group(0)) if match else {}


def find_column(columns, candidates):
    normalized = {str(col).replace(" ", ""): col for col in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return ""


def fill_identity_to_customer_table(result):
    data = load_customer_data()
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    name = result.get("姓名", "") or result.get("name", "")
    id_no = result.get("身份证号", "") or result.get("id_number", "")
    birthday = result.get("生日", "") or result.get("birthday", "") or birthday_from_id(id_no)

    name_col = find_column(columns, ["姓名", "客户姓名", "名称"]) or "姓名"
    id_col = find_column(columns, ["身份证号", "身份证号码", "证件号码", "证件号"]) or "身份证号"
    birthday_col = find_column(columns, ["生日", "出生日期", "出生年月", "出生年月日"]) or "生日"
    for col in [name_col, id_col, birthday_col]:
        if col not in columns:
            columns.append(col)
            for row in rows:
                row[col] = ""
    row = {col: "" for col in columns}
    rows.append(row)
    if name:
        row[name_col] = name
    if id_no:
        row[id_col] = id_no
    if birthday:
        row[birthday_col] = birthday
    save_customer_data({"columns": columns, "rows": rows})
    return {"name": name, "id_no": id_no, "birthday": birthday, "columns": columns, "rows": rows}


def is_today_birthday(value):
    text = str(value).strip()
    for pattern in [r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", r"(\d{1,2})[-/月](\d{1,2})"]:
        match = re.search(pattern, text)
        if match:
            month = int(match.group(len(match.groups()) - 1))
            day = int(match.group(len(match.groups())))
            today = date.today()
            return month == today.month and day == today.day
    return False


def render_template(template, row):
    text = template or ""
    for key, value in row.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def build_birthday_events(settings=None, data=None):
    settings = settings or load_customer_settings()
    data = data or load_customer_data()
    phone_col = settings.get("phone_column")
    birthday_col = settings.get("birthday_column")
    if not phone_col or not birthday_col:
        return []
    events = []
    for row in data.get("rows", []):
        if is_today_birthday(row.get(birthday_col, "")):
            phone = str(row.get(phone_col, "")).strip()
            if phone:
                events.append({"phone": phone, "name": row.get("姓名", ""), "message": render_template(settings.get("birthday_template", ""), row)})
    return events


def build_merchant_events(settings=None, data=None):
    settings = settings or load_customer_settings()
    data = data or load_customer_data()
    merchant_phone = settings.get("merchant_phone", "").strip()
    birthday_col = settings.get("birthday_column")
    if not merchant_phone or not birthday_col:
        return []
    events = []
    for row in data.get("rows", []):
        if is_today_birthday(row.get(birthday_col, "")):
            events.append({"phone": merchant_phone, "name": "订单需求", "message": render_template(settings.get("merchant_template", ""), row)})
    return events


def send_sms_email(events, receiver):
    app_config = load_config()
    sender = app_config.get("sender_email", "")
    password = app_config.get("auth_code", "")
    if not sender or not password or not receiver:
        append_log("生日提醒未发送：缺少发件邮箱、授权码或短信中转邮箱。")
        return
    for index, event in enumerate(events):
        body = json.dumps(event, ensure_ascii=False)
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header("BondTrigger", "utf-8")
        msg["From"] = sender
        msg["To"] = receiver
        send_mail(sender, password, [receiver], msg)


def check_birthday_jobs(force=False):
    settings = load_customer_settings()
    if not settings.get("birthday_enabled") and not force:
        return {"sent": False, "reason": "birthday reminder disabled", "customer_count": 0, "merchant_count": 0}
    now = datetime.now()
    if not force and now.strftime("%H:%M") != settings.get("send_time", "09:00"):
        return {"sent": False, "reason": "not scheduled time", "customer_count": 0, "merchant_count": 0}
    today = date.today().isoformat()
    if not force and settings.get("last_sent_date") == today:
        return {"sent": False, "reason": "already sent today", "customer_count": 0, "merchant_count": 0}

    data = load_customer_data()
    events = build_birthday_events(settings, data)
    merchant_events = build_merchant_events(settings, data)
    gateway = load_config().get("daily_email_receiver", "")
    if events:
        send_sms_email(events, gateway)
    if merchant_events:
        send_sms_email(merchant_events, gateway)
    settings["last_sent_date"] = today
    save_customer_settings(settings)
    if events or merchant_events:
        append_log(f"生日提醒已处理：客户 {len(events)} 条，订单 {len(merchant_events)} 条")
    return {"sent": bool(events or merchant_events), "customer_count": len(events), "merchant_count": len(merchant_events)}
