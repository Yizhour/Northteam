# NorthTeam2 Vue Frontend

Vue/Vite frontend for the NorthTeam2 workspace.

## Local Development

Run Django API first:

```powershell
cd D:\Files\NorthTeam
.\.venv\Scripts\Activate.ps1
python manage.py runserver 127.0.0.1:8010
```

Run Vue frontend:

```powershell
cd D:\Files\NorthTeam\frontend
npm install --cache .\.npm-cache
npm run dev
```

Open:

```text
http://127.0.0.1:5173/
```

Vite proxies `/api`, `/accounts`, `/admin`, and `/tools/bond-reminder` to Django.

## Production

Build static assets with:

```powershell
npm run build
```

Deploy `frontend/dist/` with Nginx as the web frontend, and proxy `/api/`, `/admin/`, `/accounts/`, and `/tools/bond-reminder/` to Django/Gunicorn.
