import copy
import json
import os
import shutil
from pathlib import Path

import pandas as pd
from django.apps import apps
from django.conf import settings
from django.db import DatabaseError, transaction

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

STORE_CONFIG = "config"
STORE_CONTACTS = "contacts"
STORE_CUSTOMER_SETTINGS = "customer_settings"
STORE_BOND_META = "bond_table_meta"
STORE_CUSTOMER_META = "customer_table_meta"
TABLE_BOND = "bond"
TABLE_CUSTOMER = "customer"


def _same_path(left, right):
    try:
        return Path(left).resolve() == Path(right).resolve()
    except Exception:
        return Path(left) == Path(right)


def _json_store_mapping(path):
    if _same_path(path, CONFIG_FILE):
        return STORE_CONFIG, DEFAULT_CONFIG
    if _same_path(path, CONTACTS_FILE):
        return STORE_CONTACTS, []
    if _same_path(path, CUSTOMER_SETTINGS_FILE):
        return STORE_CUSTOMER_SETTINGS, DEFAULT_CUSTOMER_SETTINGS
    return None, None


def _models():
    if not settings.configured or not apps.ready:
        return None, None
    try:
        store_model = apps.get_model("bondreminder", "BondReminderStore")
        row_model = apps.get_model("bondreminder", "BondReminderTableRow")
        return store_model, row_model
    except LookupError:
        return None, None


def _database_ready():
    store_model, _ = _models()
    if store_model is None:
        return False
    try:
        store_model.objects.exists()
        return True
    except DatabaseError:
        return False


def _load_store(key, default):
    store_model, _ = _models()
    if store_model is None:
        return copy.deepcopy(default)
    try:
        item, _ = store_model.objects.get_or_create(
            key=key,
            defaults={"value": copy.deepcopy(default)},
        )
        return copy.deepcopy(item.value)
    except DatabaseError:
        return copy.deepcopy(default)


def _save_store(key, value):
    store_model, _ = _models()
    if store_model is None:
        return value
    item, _ = store_model.objects.get_or_create(key=key, defaults={"value": value})
    item.value = value
    item.save(update_fields=["value", "updated_at"])
    return value


def _cell_to_json(value):
    if pd.isna(value):
        return ""
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _save_table(table_key, df, source_path=""):
    _, row_model = _models()
    if row_model is None:
        return
    columns = [str(col).strip().replace("\n", "") for col in df.columns]
    records = []
    for row_index, (_, row) in enumerate(df.iterrows()):
        records.append(
            row_model(
                table_key=table_key,
                row_index=row_index,
                data={column: _cell_to_json(row[column]) for column in columns},
            )
        )
    meta_key = STORE_BOND_META if table_key == TABLE_BOND else STORE_CUSTOMER_META
    with transaction.atomic():
        row_model.objects.filter(table_key=table_key).delete()
        if records:
            row_model.objects.bulk_create(records, batch_size=500)
        _save_store(
            meta_key,
            {
                "columns": columns,
                "total_rows": len(records),
                "source_path": str(source_path),
            },
        )


def _load_table_dataframe(table_key, nrows=None):
    _, row_model = _models()
    if row_model is None:
        return None
    try:
        meta_key = STORE_BOND_META if table_key == TABLE_BOND else STORE_CUSTOMER_META
        meta = _load_store(meta_key, {"columns": [], "total_rows": 0, "source_path": ""})
        query = row_model.objects.filter(table_key=table_key).order_by("row_index")
        if nrows is not None:
            query = query[:nrows]
        rows = [item.data for item in query]
        if not rows and not meta.get("columns"):
            return None
        columns = [str(col) for col in meta.get("columns", [])]
        df = pd.DataFrame(rows)
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        if columns:
            df = df[columns]
        return df
    except DatabaseError:
        return None


def has_bond_table():
    _, row_model = _models()
    if row_model is None:
        return BOND_CACHE_FILE.exists()
    try:
        return row_model.objects.filter(table_key=TABLE_BOND).exists()
    except DatabaseError:
        return BOND_CACHE_FILE.exists()


def read_json(path, default):
    ensure_directories()
    path = Path(path)
    store_key, store_default = _json_store_mapping(path)
    if store_key and _database_ready():
        return _load_store(store_key, store_default)
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
    store_key, _ = _json_store_mapping(path)
    if store_key and _database_ready():
        _save_store(store_key, data)
        return
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
    if _database_ready():
        df = _load_table_dataframe(TABLE_CUSTOMER)
        meta = _load_store(STORE_CUSTOMER_META, {"columns": [], "total_rows": 0})
        if df is not None:
            columns = [str(col) for col in meta.get("columns", list(df.columns))]
            rows = df.fillna("").astype(str).to_dict(orient="records")
            return {"columns": columns, "rows": rows}
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
    if _database_ready():
        columns = [str(col).strip() for col in data.get("columns", [])]
        df = pd.DataFrame(data.get("rows", []))
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        if columns:
            df = df[columns]
        _save_table(TABLE_CUSTOMER, df)
        return
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
    if _same_path(path, BOND_CACHE_FILE) and _database_ready():
        df = _load_table_dataframe(TABLE_BOND, nrows=nrows)
        if df is not None:
            return df
    ext = path.suffix.lower()
    if ext == ".csv":
        last_error = None
        for encoding in ["utf-8-sig", "gb18030", "gbk"]:
            try:
                df = pd.read_csv(path, header=header, encoding=encoding, nrows=nrows, sep=None, engine="python")
                break
            except UnicodeDecodeError as exc:
                last_error = exc
        else:
            raise last_error
    else:
        df = pd.read_excel(path, header=header, nrows=nrows)
    df.columns = [str(col).strip().replace("\n", "") for col in df.columns]
    return df


def cache_bond_table(source_path, header=0):
    df = read_table(source_path, header=header)
    if _database_ready():
        _save_table(TABLE_BOND, df, source_path=source_path)
    else:
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
    if _database_ready():
        df = _load_table_dataframe(TABLE_BOND)
        if df is None:
            return {"columns": [], "rows": [], "total_rows": 0, "path": ""}
        preview = df.head(limit).fillna("").astype(str)
        meta = _load_store(STORE_BOND_META, {"source_path": str(BOND_CACHE_FILE)})
        return {
            "columns": [str(col) for col in df.columns],
            "rows": preview.to_dict(orient="records"),
            "total_rows": int(len(df)),
            "path": meta.get("source_path") or str(BOND_CACHE_FILE),
        }
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
