# BondReminder

付息兑付提醒工具，作为 NorthTeam2 的内部工具挂载在 Django 项目中。

## 当前集成方式

- 工具源码位置：`tools/bondreminder/`
- Django 访问路径：`/tools/bond-reminder/`
- Django 入口：`tools/bondreminder/django_app/`
- 工具核心业务逻辑保留在 `app/`，HTTP 适配层已改为 Django。

## 目录说明

- `app/`：业务逻辑、模板和静态资源。
- `django_app/`：Django URL、视图和权限适配层。
- `data/`：运行时配置、通讯录、客户数据、债券缓存数据，本目录不提交到 Git。
- `uploads/`：浏览器上传的 Excel、CSV、图片、PDF，本目录只提交 `.gitkeep`。
- `outputs/`：预留输出目录，本目录只提交 `.gitkeep`。
- `logs/`：运行日志目录，本目录只提交 `.gitkeep`。
- `scripts/`：原工具保留的启动和迁移脚本。

## 本地访问

在项目根目录启动 NorthTeam2：

```powershell
python manage.py runserver 127.0.0.1:8010
```

然后访问：

```text
http://127.0.0.1:8010/tools/bond-reminder/
```

## 部署提示

此工具包含定时提醒能力。若生产环境 Gunicorn 使用多个 worker，建议设置：

```text
ENABLE_SCHEDULER=0
```

并单独运行一个调度进程，避免周报、日报、生日提醒等任务重复发送。
