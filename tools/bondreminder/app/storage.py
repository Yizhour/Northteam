import copy
import json
import os
import shutil
from pathlib import Path

import pandas as pd

from .config import (
    BOND_CACHE_FILE,
    CONFIG_FILE,
    CONTACTS_FILE,
    CUSTOMER_DATA_FILE,
    CUSTOMER_SETTINGS_FILE,
    DATA_DIR,
    FILES_DIR,
    ensure_directories,
)


DEFAULT_CONFIG = {
    "sender_email": "",
    "auth_code": "",
    "auth_expiry_enabled": False,
    "auth_start_date": "2025-01-01",
    "auth_validity_days": 180,
    "receiver_list": [],
    "excel_path": str(BOND_CACHE_FILE),
    "common_time": "09:00",
    "weekly_time": "09:00",
    "daily_time": "09:00",
    "weekly_enabled": True,
    "schedule_day": "Monday",
    "daily_enabled": False,
    "col_contact_name": "对接人姓名",
    "col_contact_phone": "对接人手机号",
    "daily_email_receiver": "",
    "send_interval_seconds": 30,
    "birthday_send_interval_seconds": 30,
    "smtp_preferred_mode": "auto",
    "smtp_timeout_seconds": 8,
    "daily_msg_template": "”{证券简称}“ {短信文本}",
    "daily_msg_intro": "您好，今日有{n}项债券事项需要处理：",
    "header_row_index": 0,
    "date_columns": [],
    "display_columns": [],
    "column_colors": {},
    "column_sms_texts": {},
    "default_column_mappings": {
        "date_columns": [
            "起息日",
            "行权公告日公司债T-30日/协会产品T-20日",
            "文件准备日（T-10）",
            "付息公告日（T-5）",
            "募集资金划付（T-2/T-1）",
            "2026年度付息日（T）",
        ],
        "display_columns": [
            "证券代码",
            "证券名称",
            "期限",
            "2026年度付息日（T）",
            "事项（付息、回售、到期)",
        ],
        "column_sms_texts": {
            "起息日": "起息日",
            "行权公告日公司债T-30日/协会产品T-20日": "行权公告",
            "文件准备日（T-10）": "准备文件",
            "付息公告日（T-5）": "付息公告",
            "募集资金划付（T-2/T-1）": "募集资金划付到账",
            "2026年度付息日（T）": "付息日",
        },
    },
    "email_subject": "【付息兑付提醒】本周债券业务关键节点提醒",
    "email_intro": "您好，本周有以下债券业务需要关注：",
    "ui_original_path": "",
    "ui_header_row_index": 0,
    "schedule_time": "09:00",
    "custom_tasks": [],
    "customer_sms_gateway_email": "",
}

DEFAULT_CUSTOMER_SETTINGS = {
    "api_key": "",
    "model": "doubao-seed-2-0-lite-260428",
    "api_url": "https://ark.cn-beijing.volces.com/api/v3/responses",
    "birthday_enabled": False,
    "phone_column": "",
    "birthday_column": "",
    "send_time": "09:00",
    "birthday_template": "生日快乐，{姓名}！祝您身体健康，万事顺意。",
    "merchant_phone": "",
    "merchant_gateway_email": "",
    "merchant_template": "客户{姓名}今天生日，请准备{是否需要蛋糕/鲜花}。客户电话：{电话号}，生日：{生日}。",
    "last_sent_date": "",
    "sms_gateway_email": "",
}

DEFAULT_CUSTOMER_DATA = {"columns": [], "rows": []}


def read_json(path, default):
    ensure_directories()
    path = Path(path)
    if not path.exists():
        write_json(path, default)
        return copy.deepcopy(default)
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return copy.deepcopy(default)


def write_json(path, data):
    ensure_directories()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    tmp_path.replace(path)


def load_config():
    data = read_json(CONFIG_FILE, DEFAULT_CONFIG)
    if "receiver_email" in data and isinstance(data["receiver_email"], str):
        import re

        emails = [item.strip() for item in re.split(r"[;\n,]", data["receiver_email"]) if item.strip()]
        data["receiver_list"] = [{"email": email, "remark": ""} for email in emails]
        data.pop("receiver_email", None)
    data.pop("daily_email_subject", None)
    data.pop("daily_link_url", None)
    data.pop("auth_code_set", None)
    for key, value in DEFAULT_CONFIG.items():
        data.setdefault(key, copy.deepcopy(value))
    if not data.get("send_interval_seconds"):
        data["send_interval_seconds"] = data.get("birthday_send_interval_seconds", 30)
    if not data.get("weekly_time"):
        data["weekly_time"] = data.get("common_time", "09:00")
    if not data.get("daily_time"):
        data["daily_time"] = data.get("common_time", "09:00")
    data["excel_path"] = str(BOND_CACHE_FILE)
    return data


def save_config(data):
    merged = load_config()
    merged.update(data)
    merged["excel_path"] = str(BOND_CACHE_FILE)
    write_json(CONFIG_FILE, merged)
    return merged


def public_config(data=None):
    data = copy.deepcopy(data or load_config())
    if data.get("auth_code"):
        data["auth_code"] = ""
        data["auth_code_set"] = True
    else:
        data["auth_code_set"] = False
    return data


def load_contacts():
    data = read_json(CONTACTS_FILE, [])
    return data if isinstance(data, list) else []


def save_contacts(data):
    write_json(CONTACTS_FILE, data if isinstance(data, list) else [])


def load_customer_data():
    data = read_json(CUSTOMER_DATA_FILE, DEFAULT_CUSTOMER_DATA)
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_CUSTOMER_DATA)
    data.setdefault("columns", [])
    data.setdefault("rows", [])
    return data


def save_customer_data(data):
    data = data if isinstance(data, dict) else copy.deepcopy(DEFAULT_CUSTOMER_DATA)
    data.setdefault("columns", [])
    data.setdefault("rows", [])
    write_json(CUSTOMER_DATA_FILE, data)


def load_customer_settings():
    data = read_json(CUSTOMER_SETTINGS_FILE, DEFAULT_CUSTOMER_SETTINGS)
    for key, value in DEFAULT_CUSTOMER_SETTINGS.items():
        data.setdefault(key, copy.deepcopy(value))
    return data


def save_customer_settings(data):
    merged = load_customer_settings()
    merged.update(data)
    write_json(CUSTOMER_SETTINGS_FILE, merged)
    return merged


def public_customer_settings(data=None):
    data = copy.deepcopy(data or load_customer_settings())
    if data.get("api_key"):
        data["api_key"] = ""
        data["api_key_set"] = True
    else:
        data["api_key_set"] = False
    return data


def read_table(path, header=0, nrows=None):
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".csv":
        try:
            df = pd.read_csv(path, header=header, encoding="utf-8-sig", nrows=nrows)
        except UnicodeDecodeError:
            df = pd.read_csv(path, header=header, encoding="gbk", nrows=nrows)
    else:
        df = pd.read_excel(path, header=header, nrows=nrows)
    df.columns = [str(col).strip().replace("\n", "") for col in df.columns]
    return df


def cache_bond_table(source_path, header=0):
    df = read_table(source_path, header=header)
    BOND_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(BOND_CACHE_FILE, index=False, encoding="utf-8-sig")
    config = load_config()
    config["excel_path"] = str(BOND_CACHE_FILE)
    config["ui_original_path"] = str(source_path)
    config["ui_header_row_index"] = int(header)
    save_config(config)
    return df


def bond_preview(limit=50):
    config = load_config()
    path = Path(config.get("excel_path") or BOND_CACHE_FILE)
    if not path.exists():
        return {"columns": [], "rows": [], "total_rows": 0, "path": ""}
    df = read_table(path, header=0)
    preview = df.head(limit).fillna("").astype(str)
    return {
        "columns": [str(col) for col in df.columns],
        "rows": preview.to_dict(orient="records"),
        "total_rows": int(len(df)),
        "path": str(path),
    }


def import_customer_table(path):
    df = read_table(path, header=0).fillna("")
    data = {
        "columns": [str(col).strip() for col in df.columns],
        "rows": [{str(col).strip(): str(row[col]) for col in df.columns} for _, row in df.iterrows()],
    }
    save_customer_data(data)
    return data


def copy_initial_assets(project_root):
    ensure_directories()
    root = Path(project_root)
    for name, dst in [
        ("config.json", CONFIG_FILE),
        ("contacts.json", CONTACTS_FILE),
        ("customer_data.json", CUSTOMER_DATA_FILE),
        ("customer_settings.json", CUSTOMER_SETTINGS_FILE),
        ("bond_data_cache.csv", BOND_CACHE_FILE),
    ]:
        src = root / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
    src_files = root / "files"
    if src_files.exists():
        for child in src_files.iterdir():
            if child.is_file() and not child.name.startswith("~$"):
                dst = FILES_DIR / child.name
                if not dst.exists():
                    shutil.copy2(child, dst)
