# BEL Secure Checksheet Portal

Full-stack checksheet processing: FastAPI backend + React (Vite) frontend.

## Prerequisites

- Python 3.10+
- Node.js 18+

## Backend setup

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run from the `backend` folder so `database` and `app` imports resolve correctly.

The SQLite database is created automatically at `backend/database/checksheet.db` on first startup.

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 (or the URL Vite prints).

## Demo accounts

| Role     | Username       | Password              |
|----------|----------------|-----------------------|
| Admin    | `bel_admin`    | `Admin@BEL#2025!`     |
| Engineer | `bel_engineer` | `Engineer@BEL#2025!`  |
| Viewer   | `bel_viewer`   | `Viewer@BEL#2025!`    |

## Features

- JWT login with refresh tokens and role-based access (admin / engineer / viewer)
- PDF upload with template matching from SQLite
- Pass/fail evaluation and report persistence
- Saved reports history and admin audit logs
