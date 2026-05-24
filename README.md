# CRMS — Crime Record Management System

A police investigation dashboard for the Bengaluru Police Department, built with Flask, MySQL, and a React-powered single-page frontend. CRMS supports officer case management, citizen complaint intake, automated case assignment, and a secure case-access request workflow with PDF dossier delivery.

## Features

- **Staff portal** — Role-based login, case CRUD, officer assignments, analytics, and case status updates
- **Public portal** — Citizens can file complaints and request access to case records (reCAPTCHA protected)
- **Automated assignment** — Background scheduler promotes pending complaints to cases and assigns officers by crime severity and workload
- **Access request workflow** — Officers approve or reject citizen dossier requests; approved requests trigger a PDF case dossier via email (or mock mode)
- **Security** — bcrypt password hashing, invisible reCAPTCHA on public forms and login, role-based case visibility, `X-Officer-Id` header on protected routes

## Contents

| Path | Description |
|------|-------------|
| `Backend/` | Flask API, SQL migrations, assignment engine, email/PDF utilities |
| `Frontend/crms_frontend.html` | React UI (CDN-based) served at `/` |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |

## Prerequisites

- Python 3.10+
- MySQL 8.x
- Google reCAPTCHA v2 (invisible) keys — [reCAPTCHA admin](https://www.google.com/recaptcha/admin) (test keys work on localhost)

## Quick Start

### 1. Clone and configure environment

```bash
cp .env.example .env
```

Edit `.env` with your MySQL credentials and reCAPTCHA keys. See [Environment Variables](#environment-variables) for the full list.

> Do not commit `.env` to source control.

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Initialize the database

Run the scripts **in order** against your MySQL server:

```bash
mysql -u root -p < Backend/setup_db.sql
mysql -u root -p < Backend/migrate_v2.sql
mysql -u root -p < Backend/migrate_v3.sql
```

Replace `root` with your MySQL user if different. Each script is additive and safe to re-run where noted (`CREATE TABLE IF NOT EXISTS`, etc.).

| Script | Purpose |
|--------|---------|
| `setup_db.sql` | Core schema, seed officers and sample cases |
| `migrate_v2.sql` | Officer auth (`password_hash`, `role`), public complaints staging |
| `migrate_v3.sql` | Case access requests table and seed data |

### 4. Start the server

```bash
python3 Backend/app.py
```

Expected startup banner:

```text
============================================================
  CRMS Flask API — Bengaluru Police Department
============================================================
```

Open **http://localhost:5000** in your browser. The Flask app serves the frontend and API from the same origin.

### 5. Sign in (development)

After running `migrate_v2.sql`, seeded officers use this default password:

| Field | Value |
|-------|-------|
| Password | `crms1234` |
| Badge ID | e.g. `BPD-7821` (Inspector Arjun Nair) |

Inspectors (`Inspector Arjun Nair`, `Inspector Vikram Rao`, `Inspector Meera Iyer`) can create and edit cases. Other seeded officers are **viewer** (read-only for assigned cases). Change passwords before any production deployment.

## Environment Variables

All runtime configuration is loaded from `.env` via `python-dotenv` in `Backend/config.py`.

### Database (required)

| Variable | Description |
|----------|-------------|
| `DB_HOST` | MySQL host |
| `DB_PORT` | MySQL port (default `3306`) |
| `DB_USER` | MySQL username |
| `DB_PASSWORD` | MySQL password |
| `DB_NAME` | Database name (`crms`) |

### Flask (required)

| Variable | Description |
|----------|-------------|
| `FLASK_HOST` | Bind address (`0.0.0.0` or `127.0.0.1`) |
| `FLASK_PORT` | Port (default `5000`) |
| `FLASK_DEBUG` | `true` or `false` |

### CORS (optional)

| Variable | Description |
|----------|-------------|
| `CORS_ORIGIN` | Allowed origin (`*` for dev; set to your domain in production) |

### reCAPTCHA v2 invisible (required in config)

| Variable | Description |
|----------|-------------|
| `RECAPTCHA_SECRET_KEY` | Server-side secret key |
| `RECAPTCHA_PUBLIC_KEY` | Site key (used by the frontend) |
| `RECAPTCHA_THRESHOLD` | Reserved for v3 scoring (unused for v2) |

For local testing without verification, you can leave `RECAPTCHA_SECRET_KEY` empty — the backend skips CAPTCHA checks when the secret is missing.

### SMTP email (optional)

When SMTP is not configured, approved access requests are written to `Backend/mock_emails/` as JSON logs and PDF files instead of sending live email.

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP server (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (e.g. `587`) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `SMTP_FROM_EMAIL` | Sender address |
| `SMTP_FROM_NAME` | Sender display name |

## Project Structure

```text
.
├── .env.example
├── requirements.txt
├── Backend/
│   ├── app.py                  # Flask routes and startup
│   ├── config.py               # Environment configuration
│   ├── db_connection.py        # MySQL connection pool
│   ├── queries.py              # All SQL / data access
│   ├── assignment_algorithm.py # Auto-assign pending complaints
│   ├── email_utils.py          # PDF dossier + SMTP / mock email
│   ├── setup_db.sql
│   ├── migrate_v2.sql
│   ├── migrate_v3.sql
│   └── mock_emails/            # Offline email/PDF output (dev)
└── Frontend/
    └── crms_frontend.html      # Public portal + staff dashboard
```

## API Overview

Responses use `{ "success": true, "data": ... }` or `{ "success": false, "error": "..." }`.

Protected staff routes expect the **`X-Officer-Id`** header (integer officer ID returned from login).

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |

### Cases

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/cases`, `/api/cases` | List cases (filters, pagination; role-based visibility) |
| `GET` | `/cases/<id>`, `/api/cases/<id>` | Case detail with assigned officers |
| `POST` | `/cases` | Create case (inspector role) |
| `PATCH` | `/cases/<id>` | Update case fields / status |
| `DELETE` | `/cases/<id>` | Delete case and assignments |
| `GET` | `/cases/<id>/officers` | Officers assigned to a case |

Query parameters for list: `status`, `crime_type`, `location`, `search`, `page`, `limit`.

### Officers & assignments

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/officers` | List officers |
| `POST` | `/officers` | Add officer |
| `GET` | `/case-officer` | All case–officer pairings |
| `POST` | `/case-officer` | Assign officer to case |
| `DELETE` | `/case-officer` | Remove assignment |

### Analytics & assignment engine

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analytics` | Dashboard analytics |
| `GET` | `/assignments/pending` | Queue of complaints awaiting auto-assignment |
| `POST` | `/assignments/process` | Manually run the assignment algorithm |

A background thread also runs the assignment algorithm every **10 seconds** while the server is running.

### Public portal (citizen)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/public/complaint` | Submit a complaint (staged for review / auto-promotion) |
| `POST` | `/public/access-request` | Request access to a case dossier |
| `GET` | `/stats` | Public statistics summary |

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login` | Officer login (`badge_id`, `password`, `captcha_token`) |

No JWT in this MVP — the client stores the officer record and sends `X-Officer-Id` on subsequent requests. Write endpoints validate role server-side.

### Public complaints (staff review)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/public-complaints` | List staged complaints (`?status=Pending`) |
| `POST` | `/public-complaints/<id>/promote` | Promote complaint to a full case |
| `POST` | `/public-complaints/<id>/reject` | Reject complaint |

### Case access requests (staff)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/access-requests` | List access requests (visibility by role/assignment) |
| `POST` | `/api/access-requests/<id>/approve` | Approve; sends PDF dossier email async |
| `POST` | `/api/access-requests/<id>/reject` | Reject; sends decline notification async |

## Frontend

The UI is a single HTML file using React, Tailwind CSS, Chart.js, and Framer Motion from CDNs.

| View | Description |
|------|-------------|
| **Public portal** | File complaints, request case access, view public stats |
| **Staff login** | Badge ID + password with reCAPTCHA |
| **Staff dashboard** | Cases (filter, paginate, update status), access request queue, analytics |

reCAPTCHA site key is read from the backend environment at runtime.

## Automated Case Assignment

When a citizen files a complaint, it lands in `public_complaints` with status `Pending`. The assignment engine (`assignment_algorithm.py`):

1. Maps `crime_type` to severity (e.g. Assault → Critical, Cyber Fraud → High)
2. Selects officers by rank, current workload, and seniority
3. Creates a case with `source='public'` and `case_officer` rows
4. Marks the complaint as `Promoted`

Inspectors and admins see all cases; viewers only see cases they are assigned to.

## Email & PDF Dossiers

On access request approval, `email_utils.py` generates a ReportLab PDF dossier and dispatches it asynchronously:

- **SMTP configured** — Email sent to the requester with the PDF attached
- **SMTP not configured** — Mock mode writes `email_*.json` and `*.pdf` under `Backend/mock_emails/`

Rejections send a notification email (or mock log) without an attachment.

## Security & Production

- Never commit `.env` or real credentials.
- Change default officer passwords from `migrate_v2.sql` before deployment.
- Restrict `CORS_ORIGIN` to your trusted frontend host.
- Keep `RECAPTCHA_SECRET_KEY` and `SMTP_PASSWORD` secret.
- Use HTTPS in production.
- Run behind a production WSGI server instead of the Flask dev server:

```bash
cd Backend
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

The development entrypoint calls `init_pool()` and `start_assignment_scheduler()` before `app.run()`. For Gunicorn, wire equivalent startup (e.g. a small `wsgi.py` or Gunicorn `post_fork` hook) so the DB pool and assignment scheduler are initialized in each worker as needed.

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| MySQL connection errors | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` in `.env` |
| Frontend not loading | Server running; visit `http://localhost:5000` |
| Login fails | Migrations run; badge ID exact (e.g. `BPD-7821`); password `crms1234` for dev seeds |
| CAPTCHA errors | Valid keys in `.env`, or empty `RECAPTCHA_SECRET_KEY` for local bypass |
| No email received | Configure SMTP vars, or inspect `Backend/mock_emails/` in mock mode |
| Missing access requests table | Run `Backend/migrate_v3.sql` |

## Dependencies

| Package | Role |
|---------|------|
| Flask | Web framework |
| flask-cors | CORS |
| mysql-connector-python | MySQL driver |
| python-dotenv | `.env` loading |
| bcrypt | Password hashing |
| requests | reCAPTCHA verification |
| reportlab | PDF dossier generation |
| gunicorn | Production WSGI server |
