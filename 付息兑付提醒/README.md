# BondReminder Pro Web

这是原 PyQt5 桌面版的 Linux Web 部署版本，保留债券付息兑付提醒、每日自查、通讯录、自定义发送任务、客户管理、身份证识别和生日提醒逻辑。

## 目录

- `app/`：Flask 后端、页面模板、静态资源
- `data/`：配置、通讯录、客户表、债券缓存 CSV、原始示例 Excel
- `uploads/`：浏览器上传的 Excel/CSV/图片/PDF
- `outputs/`：预留结果输出目录
- `logs/`：预留目录；页面日志仅在服务运行期间保存在内存中，不写入文件
- `scripts/`：迁移和启动脚本

## 本地运行

```bash
cd deploy_web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

浏览器访问 `http://服务器IP:8000`。

## Linux 生产部署

```bash
cd deploy_web
cp .env.example .env
bash scripts/run.sh
```

默认使用 Gunicorn 单 worker，并启用内置调度器。若使用多个 worker，请设置 `ENABLE_SCHEDULER=0`，并单独启动一个只跑调度的进程，避免周报、日报、生日提醒重复发送。

## 数据与配置

迁移后的运行数据位于 `data/`。Web 版会把上传的债券 Excel/CSV 缓存为 `data/bond_data_cache.csv`，所有后续扫描都读取该缓存，保持原桌面版行为一致。

敏感字段如邮箱授权码、Volcengine Ark API Key 只保存在后端 JSON 文件中。页面读取配置时会隐藏这些字段；需要更新时重新输入，留空则保持原值。

## 邮件与短信中转

邮件仍使用 `smtp.163.com:465`。日报、生日提醒和短信模式自定义任务仍以 `BondTrigger` 为标题，并将 JSON 内容用 `&` 拼接后发送到短信中转邮箱，保持原脚本识别格式。
