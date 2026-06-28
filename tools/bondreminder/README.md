# BondReminder

付息兑付提醒工具，作为 NorthTeam 的内部工具挂载在 Django 项目中。

## 当前集成方式

- 工具源码位置：`tools/bondreminder/`
- Django 访问路径：`/tools/bond-reminder/`
- Django 入口：`tools/bondreminder/django_app/`
- 核心业务逻辑保留在 `app/`，HTTP 适配层由 Django 提供。

## 数据存储

当前版本只使用 Django 数据库保存业务数据。部署到 MySQL 后，以下内容都会存入 MySQL：

- `BondReminderStore`：配置、通讯录、客户提醒设置、表格元信息。
- `BondReminderTableRow`：债券表和客户表的逐行数据。

浏览器上传的 Excel/CSV/图片/PDF 会先保存为临时文件用于解析，接口结束后立即删除，不会作为原件长期保存。

`data/` 目录中的旧 JSON/CSV 文件不再作为运行时数据来源；如服务器上存在旧文件，可以仅作为人工备份处理。

## 目录说明

- `app/`：业务逻辑、模板和静态资源。
- `django_app/`：Django URL、视图、模型、迁移和权限适配层。
- `uploads/`：临时上传目录，只提交 `.gitkeep`。
- `outputs/`：预留输出目录，只提交 `.gitkeep`。
- `logs/`：运行日志目录，只提交 `.gitkeep`。
- `scripts/`：本地启动辅助脚本。

## 本地访问

在项目根目录启动 NorthTeam：

```powershell
python manage.py runserver 127.0.0.1:8010
```

然后访问：

```text
http://127.0.0.1:8010/tools/bond-reminder/
```

## 部署提示

此工具包含定时提醒能力。如果生产环境 Gunicorn 使用多个 worker，建议设置：

```text
ENABLE_SCHEDULER=0
```

并单独运行一个调度进程，避免周报、日报、生日提醒等任务重复发送。
