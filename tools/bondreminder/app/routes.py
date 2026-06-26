import copy
import os
import re
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request
from werkzeug.utils import secure_filename

from .bond_logic import BondReminder
from .config import BOND_CACHE_FILE, UPLOAD_DIR
from .customer_logic import call_identity_ai, check_birthday_jobs, fill_identity_to_customer_table
from .logging_utils import append_log, clear_logs, read_logs
from .scheduler import scheduler_service
from .storage import (
    bond_preview,
    cache_bond_table,
    import_customer_table,
    load_config,
    load_contacts,
    load_customer_data,
    load_customer_settings,
    public_config,
    public_customer_settings,
    save_config,
    save_contacts,
    save_customer_data,
    save_customer_settings,
)

bp = Blueprint("web", __name__)

ALLOWED_TABLE_EXTENSIONS = {".xlsx", ".xls", ".csv"}
ALLOWED_IDENTITY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".pdf"}


def ok(data=None, **kwargs):
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload)


def error(message, status=400):
    append_log(f"请求失败: {message}")
    return jsonify({"ok": False, "error": str(message)}), status


def save_upload(file_storage, allowed_exts):
    if not file_storage or not file_storage.filename:
        raise ValueError("未上传文件")
    ext = Path(file_storage.filename).suffix.lower()
    if ext not in allowed_exts:
        raise ValueError(f"不支持的文件类型: {ext}")
    safe_name = secure_filename(file_storage.filename) or f"upload{ext}"
    filename = f"{uuid.uuid4().hex}_{safe_name}"
    path = UPLOAD_DIR / filename
    file_storage.save(path)
    return path


def preserve_secret_update(current, incoming, key):
    if key not in incoming:
        return
    if incoming.get(key):
        current[key] = incoming[key]
    elif incoming.get(f"clear_{key}"):
        current[key] = ""


@bp.route("/")
def index():
    return render_template("index.html")


@bp.get("/api/config")
def api_get_config():
    return ok(public_config())


@bp.post("/api/config")
def api_save_config():
    incoming = request.get_json(force=True, silent=True) or {}
    current = load_config()
    auth_code = current.get("auth_code", "")
    current.update(incoming)
    current["auth_code"] = auth_code
    preserve_secret_update(current, incoming, "auth_code")
    saved = save_config(current)
    scheduler_service.restart()
    append_log("债券配置已保存。")
    return ok(public_config(saved))


@bp.post("/api/upload/bond-data")
def api_upload_bond_data():
    try:
        header = int(request.form.get("header", request.form.get("header_row_index", 0)) or 0)
        path = save_upload(request.files.get("file"), ALLOWED_TABLE_EXTENSIONS)
        df = cache_bond_table(path, header)
        config = load_config()
        columns = [str(col) for col in df.columns]
        defaults = config.get("default_column_mappings", {})
        if not config.get("date_columns"):
            config["date_columns"] = [col for col in defaults.get("date_columns", []) if col in columns]
        if not config.get("display_columns"):
            config["display_columns"] = [col for col in defaults.get("display_columns", []) if col in columns]
        save_config(config)
        scheduler_service.restart()
        append_log(f"债券数据已上传并缓存: {path.name}")
        return ok(bond_preview())
    except Exception as exc:
        return error(exc)


@bp.get("/api/bond-preview")
def api_bond_preview():
    try:
        return ok(bond_preview())
    except Exception as exc:
        return error(exc)


@bp.post("/api/run/weekly")
def api_run_weekly():
    logs = BondReminder(load_config()).run_weekly_check()
    return ok({"logs": logs})


@bp.post("/api/run/daily")
def api_run_daily():
    logs = BondReminder(load_config()).run_daily_check()
    return ok({"logs": logs})


@bp.post("/api/run/manual")
def api_run_manual():
    config = load_config()
    logs = []
    reminder = BondReminder(config)
    if config.get("weekly_enabled", True):
        logs.extend(reminder.run_weekly_check())
    if config.get("daily_enabled", False):
        logs.extend(BondReminder(config).run_daily_check())
    if not logs:
        append_log("当前未启用任何任务，无法执行调试。")
    return ok({"logs": logs})


@bp.get("/api/contacts")
def api_get_contacts():
    return ok(load_contacts())


@bp.post("/api/contacts")
def api_save_contacts():
    contacts = request.get_json(force=True, silent=True) or []
    if not isinstance(contacts, list):
        return error("通讯录必须是数组")
    phone_pattern = re.compile(r"^1[3-9]\d{9}$")
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    for idx, contact in enumerate(contacts, start=1):
        phone = str(contact.get("phone", "")).strip()
        email = str(contact.get("email", "")).strip()
        if phone and not phone_pattern.match(phone):
            return error(f"第 {idx} 行手机号格式不正确")
        if email and not email_pattern.match(email):
            return error(f"第 {idx} 行邮箱格式不正确")
    save_contacts(contacts)
    append_log("通讯录已保存。")
    return ok(load_contacts())


@bp.get("/api/tasks")
def api_get_tasks():
    return ok(load_config().get("custom_tasks", []))


@bp.post("/api/tasks")
def api_create_task():
    try:
        task = request.get_json(force=True, silent=True) or {}
        config = load_config()
        tasks = config.setdefault("custom_tasks", [])
        tasks.append(normalize_task(task))
        save_config(config)
        scheduler_service.restart()
        append_log(f"自定义任务已新增: {task.get('name', '未命名任务')}")
        return ok(tasks)
    except Exception as exc:
        return error(exc)


@bp.put("/api/tasks/<int:index>")
def api_update_task(index):
    try:
        task = request.get_json(force=True, silent=True) or {}
        config = load_config()
        tasks = config.setdefault("custom_tasks", [])
        if index < 0 or index >= len(tasks):
            return error("任务不存在", 404)
        old = tasks[index]
        new_task = normalize_task(task)
        if old.get("executed", False):
            new_task["executed"] = False
            new_task["enabled"] = True
        tasks[index] = new_task
        save_config(config)
        scheduler_service.restart()
        append_log(f"自定义任务已更新: {new_task.get('name', '未命名任务')}")
        return ok(tasks)
    except Exception as exc:
        return error(exc)


@bp.delete("/api/tasks/<int:index>")
def api_delete_task(index):
    config = load_config()
    tasks = config.setdefault("custom_tasks", [])
    if index < 0 or index >= len(tasks):
        return error("任务不存在", 404)
    removed = tasks.pop(index)
    save_config(config)
    scheduler_service.restart()
    append_log(f"自定义任务已删除: {removed.get('name', '未命名任务')}")
    return ok(tasks)


@bp.post("/api/tasks/<int:index>/toggle")
def api_toggle_task(index):
    config = load_config()
    tasks = config.setdefault("custom_tasks", [])
    if index < 0 or index >= len(tasks):
        return error("任务不存在", 404)
    task = tasks[index]
    if task.get("executed", False):
        task["executed"] = False
        task["enabled"] = True
    else:
        task["enabled"] = not task.get("enabled", True)
    save_config(config)
    scheduler_service.restart()
    append_log(f"自定义任务状态已切换: {task.get('name', '未命名任务')}")
    return ok(tasks)


@bp.post("/api/tasks/<int:index>/run")
def api_run_task(index):
    config = load_config()
    tasks = config.setdefault("custom_tasks", [])
    if index < 0 or index >= len(tasks):
        return error("任务不存在", 404)
    reminder = BondReminder(config)
    reminder.run_custom_task(tasks[index])
    return ok({"logs": reminder.logs})


def normalize_task(task):
    name = str(task.get("name", "")).strip()
    if not name:
        raise ValueError("任务名称不能为空")
    send_type = task.get("send_type", "email")
    if send_type not in {"email", "sms"}:
        raise ValueError("发送方式必须为 email 或 sms")
    receivers = [str(item).strip() for item in task.get("receivers", []) if str(item).strip()]
    if not receivers:
        raise ValueError("请至少添加一个收件人/手机号")
    time_config = task.get("time_config", {}) or {}
    time_type = time_config.get("type", "once")
    normalized_time = {"type": time_type, "time": time_config.get("time", "00:00")}
    if time_type == "once":
        normalized_time["date"] = time_config.get("date")
    elif time_type == "weekly":
        normalized_time["weekdays"] = time_config.get("weekdays", [])
    elif time_type != "daily":
        raise ValueError("不支持的发送策略")
    return {
        "name": name,
        "send_type": send_type,
        "subject": task.get("subject") or f"自定义任务：{name}",
        "receivers": receivers,
        "receiver_remarks": task.get("receiver_remarks", []),
        "time_config": normalized_time,
        "content": task.get("content", ""),
        "enabled": bool(task.get("enabled", True)),
        "executed": bool(task.get("executed", False)),
    }


@bp.get("/api/logs")
def api_logs():
    limit = int(request.args.get("limit", 2000))
    return ok(read_logs(limit))


@bp.delete("/api/logs")
def api_clear_logs():
    clear_logs()
    return ok([])


@bp.get("/api/customer-data")
def api_get_customer_data():
    return ok(load_customer_data())


@bp.post("/api/customer-data")
def api_save_customer_data():
    data = request.get_json(force=True, silent=True) or {}
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    if not isinstance(columns, list) or not isinstance(rows, list):
        return error("客户表数据格式不正确")
    save_customer_data({"columns": columns, "rows": rows})
    append_log(f"客户表已保存：{len(rows)} 行，{len(columns)} 列。")
    return ok(load_customer_data())


@bp.post("/api/upload/customer-data")
def api_upload_customer_data():
    try:
        path = save_upload(request.files.get("file"), ALLOWED_TABLE_EXTENSIONS)
        data = import_customer_table(path)
        append_log(f"客户表已导入：{path.name}，{len(data.get('rows', []))} 行，{len(data.get('columns', []))} 列。")
        return ok(data)
    except Exception as exc:
        return error(exc)


@bp.get("/api/customer-settings")
def api_get_customer_settings():
    return ok(public_customer_settings())


@bp.post("/api/customer-settings")
def api_save_customer_settings():
    incoming = request.get_json(force=True, silent=True) or {}
    current = load_customer_settings()
    api_key = current.get("api_key", "")
    current.update(incoming)
    current["api_key"] = api_key
    preserve_secret_update(current, incoming, "api_key")
    saved = save_customer_settings(current)
    append_log(
        "客户管理设置已保存："
        f"生日提醒={'启用' if saved.get('birthday_enabled') else '停用'}，"
        f"发送时间={saved.get('send_time', '')}，"
        f"手机号列={saved.get('phone_column', '') or '-'}，"
        f"生日列={saved.get('birthday_column', '') or '-'}。"
    )
    return ok(public_customer_settings(saved))


@bp.post("/api/customer/identity-ocr")
def api_identity_ocr():
    try:
        path = save_upload(request.files.get("file"), ALLOWED_IDENTITY_EXTENSIONS)
        append_log(f"开始身份证识别：{path.name}")
        settings = load_customer_settings()
        result = call_identity_ai(path, settings)
        filled = fill_identity_to_customer_table(result)
        append_log(f"身份证识别完成：姓名={filled.get('name') or '-'}，生日={filled.get('birthday') or '-'}。")
        return ok({"raw": result, "filled": filled})
    except Exception as exc:
        return error(exc)


@bp.post("/api/customer/birthday-check")
def api_birthday_check():
    try:
        result = check_birthday_jobs(force=True)
        append_log(
            "手动生日提醒检查完成："
            f"客户提醒 {result.get('customer_count', 0)} 条，"
            f"订单提醒 {result.get('merchant_count', 0)} 条，"
            f"是否发送={'是' if result.get('sent') else '否'}。"
        )
        return ok(result)
    except Exception as exc:
        return error(exc)


@bp.get("/api/health")
def api_health():
    return ok({"status": "running", "bond_cache_exists": BOND_CACHE_FILE.exists()})
