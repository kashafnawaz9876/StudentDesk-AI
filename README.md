# StudentDesk AI

StudentDesk AI is a student planner built with React, Vite, Flask, SQLAlchemy, MySQL, and Groq tool calling.

## Features

- Personal dashboard and assignment tracking
- Calendar events, reminders, and weekly timetable
- Groq AI assistant for assignments, classes, and calendar event creation
- Login and signup with Werkzeug password hashing and Flask signed sessions
- User-specific assignment, class, event, and AI history records
- Responsive purple and indigo interface

## Requirements

- Node.js 20+
- Python 3.10+
- MySQL 8+ (or SQLite for local development)
- Groq API key for live AI chat

## Backend setup (Windows PowerShell)

From `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set a private, random `SECRET_KEY` of at least 32 characters, `GROQ_API_KEY`, and `DATABASE_URL` in `backend/.env`. You can generate a key with `python -c "import secrets; print(secrets.token_hex(32))"`. Never commit or share `.env`. For production over HTTPS, set `SESSION_COOKIE_SECURE=1`. Keep `SESSION_COOKIE_SECURE=0` for local HTTP development.

### Safe database migration

The authentication migration is explicit and additive. **Back up the database before applying it.** For MySQL, for example:

```powershell
mysqldump --single-transaction studentdesk > studentdesk-pre-auth.sql
```

Stop the running backend, verify the configured database with:

```powershell
python migrate_auth.py --check
```

Then apply the migration:

```powershell
python migrate_auth.py --apply
```

The script creates missing tables and adds nullable `user_id` columns and foreign keys to the existing assignment, class, event, and AI log tables. It does not drop tables, reset records, or automatically assign old records to a new account. Existing records remain in place with `user_id = NULL` and are excluded from all authenticated users' queries. To make any legacy record visible to an account, first review and explicitly map its ownership in a separate, backed-up data migration; no automatic ownership mapping is safe because the previous app did not record who owned a row.

For a fresh local SQLite database, the same migration command creates the tables and ownership columns. The backend intentionally does not run schema changes on startup.

Start Flask after the migration:

```powershell
python app.py
```

Backend: `http://127.0.0.1:5000`.

### AWS EC2 MySQL database setup

On the EC2 instance, install and start MySQL 8, then from the project root create the database:

```bash
sudo mysql < backend/database/create_database.sql
```

Create a dedicated application user (replace the placeholder with a unique, strong password; do not use the MySQL root account for the app):

```sql
CREATE USER 'studentdesk_app'@'localhost' IDENTIFIED BY 'REPLACE_WITH_A_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON studentdesk.* TO 'studentdesk_app'@'localhost';
FLUSH PRIVILEGES;
```

Set `DATABASE_URL` in `backend/.env`, using a URL-encoded password if it contains reserved URL characters:

```text
mysql+pymysql://studentdesk_app:YOUR_PASSWORD@127.0.0.1:3306/studentdesk
```

From `backend`, run the existing migration once to create all application tables and indexes:

```bash
python migrate_auth.py --check
python migrate_auth.py --apply
```

`create_database.sql` creates only the database; `migrate_auth.py --apply` creates or safely upgrades the tables. The migration is deliberately explicit rather than running schema changes every time the app starts. Keep MySQL private, allow database connections only from the app host, and never commit `.env` or real credentials.

## Frontend setup

From `frontend`:

```powershell
npm install
copy .env.example .env
npm run dev
```

Open the Vite URL (usually `http://localhost:5173`). The local Vite configuration proxies `/api` requests to Flask, so leave `VITE_API_URL` blank for local development. For deployment, set it to the API origin and configure `FRONTEND_ORIGIN` to the exact frontend origin. Deploy frontend and API on the same site (or behind a same-origin reverse proxy) so the secure session cookie is available.

## Authentication and data ownership

- Signup requires a name, email, and password of at least 8 characters.
- Passwords are stored as Werkzeug password hashes, never as plain text.
- Login uses an HTTP-only, SameSite=Lax signed session cookie. Use HTTPS and `SESSION_COOKIE_SECURE=1` in production.
- `/api/health`, `/api/auth/login`, `/api/auth/signup`, and `/api/auth/me` are public. Dashboard, planner data, AI chat, and AI history APIs require a session.
- API queries and AI tools are scoped to the logged-in user. An attempt to update or delete another account's record returns not found.
- New accounts receive the starter timetable and assignment examples that the original app provided globally. Existing legacy records remain unassigned until deliberately mapped.

## API overview

- `GET /api/health`
- `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`
- `GET /api/dashboard`
- `GET/POST /api/assignments`
- `PATCH/DELETE /api/assignments/<id>`
- `GET/POST /api/classes`
- `GET/POST /api/events`
- `POST /api/agent/chat`
- `GET /api/agent/history`

Browser notifications require the site to be open and notification permission to be granted. Email delivery and automatic university-portal synchronization are not included.

## Tests

Run the backend auth/ownership tests from the project root:

```powershell
.\backend\venv\Scripts\python.exe -m unittest backend.test_auth
```

The tests use a temporary SQLite database and a mocked Groq response; they do not connect to or alter the configured MySQL database. Build the frontend with:

```powershell
cd frontend
npm run build
```
