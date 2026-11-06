# BGC Maintenance System

A Flask web app for managing equipment/assets and maintenance logs, with Arabic RTL UI.
Branded with the BGC logo.

## Features
- Login (Flask-Login)
- Asset registry (add / delete)
- Maintenance log registry (add / delete, with status, cost, technician, spare parts)
- Dashboard with KPIs and recent activity

## Setup (local)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then edit .env with your values
python app.py
```

Open http://127.0.0.1:5000 — default login: `admin` / `admin123`.

## Using Supabase as the database

1. Create a project at https://supabase.com
2. Go to **Project Settings → Database → Connection string (URI)** and copy it.
3. Put it in `.env` as `DATABASE_URL=postgresql://...`
4. Run the app; tables are created automatically on first start.

## Deploying

The app is WSGI-ready (gunicorn included). Example (Render/Railway/Heroku-style):

```bash
gunicorn app:app
```

Set `SECRET_KEY` and `DATABASE_URL` as environment variables in your host.

## Sharing

Push to GitHub and invite teammates, or deploy to a host for a live URL.
```<|end|><|start|>write to=assistant<|channel|>analysis<|message|>Created file successfully: README.md