# CRMS — Crime Record Management System

A police investigation dashboard built with Flask, MySQL, and a React-powered frontend. This repository includes a secure backend API, MySQL schema scripts, and a cinematic staff portal UI.

## Contents

- `Backend/` — Flask server source code
- `Frontend/` — React-based UI served from `crms_frontend.html`
- `requirements.txt` — Python dependency list
- `.env.example` — Environment variable template
- `Backend/setup_db.sql` — Schema and seed data
- `Backend/migrate_v2.sql` — Database updates for version 2

## Quick Start

### 1. Create a local `.env`

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Update values in `.env`:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_NAME=crms
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
CORS_ORIGIN=*
RECAPTCHA_SECRET_KEY=your_recaptcha_secret_key
RECAPTCHA_PUBLIC_KEY=your_recaptcha_site_key
RECAPTCHA_THRESHOLD=0.5
```

> Do not commit `.env` to source control.

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize the database

Run the SQL scripts in MySQL:

```bash
mysql -u root -p < Backend/setup_db.sql
mysql -u root -p < Backend/migrate_v2.sql
```

If your MySQL user is not `root`, change the command to use your user and password.

### 4. Start the backend server

```bash
python3 Backend/app.py
```

Expected output:

```text
============================================================
  CRMS Flask API — Bengaluru Police Department
============================================================
```

Then open:

```text
http://localhost:5000
```

The frontend UI is served from the backend root route and communicates with the Flask API.

## Environment Variables

All runtime configuration is read from environment variables. Use `.env` in development.

- `DB_HOST` — MySQL host
- `DB_PORT` — MySQL port
- `DB_USER` — MySQL username
- `DB_PASSWORD` — MySQL password
- `DB_NAME` — Database name
- `FLASK_HOST` — Flask host address
- `FLASK_PORT` — Flask port number
- `FLASK_DEBUG` — `true` or `false`
- `CORS_ORIGIN` — Allowed origin for frontend requests
- `RECAPTCHA_SECRET_KEY` — Google reCAPTCHA v2 secret key
- `RECAPTCHA_PUBLIC_KEY` — Google reCAPTCHA v2 site key
- `RECAPTCHA_THRESHOLD` — v3 score threshold (not used for v2)

## Project Structure

```text
.
├── .env.example
├── Backend/
│   ├── app.py
│   ├── config.py
│   ├── db_connection.py
│   ├── queries.py
│   ├── setup_db.sql
│   ├── migrate_v2.sql
│   └── requirements.txt
├── Frontend/
│   └── crms_frontend.html
└── requirements.txt
```

## API Overview

The backend exposes these main endpoints:

- `GET /health` — Health check
- `GET /cases` — List cases
- `GET /cases/<id>` — Get case details
- `POST /cases` — Create a new case
- `PATCH /cases/<id>` — Update a case
- `DELETE /cases/<id>` — Delete a case
- `GET /cases/<id>/officers` — Get assigned officers for a case
- `GET /officers` — List officers
- `POST /officers` — Add a new officer
- `GET /case-officer` — List case-officer assignments
- `POST /case-officer` — Assign an officer to a case
- `DELETE /case-officer` — Remove assignment
- `GET /analytics` — Analytics summary
- `POST /public/complaint` — Submit a citizen complaint
- `POST /public/access-request` — Request public access
- `GET /stats` — Public stats summary
- `POST /auth/login` — Officer login
- `GET /public-complaints` — List public complaints (staff)
- `POST /public-complaints/<id>/promote` — Promote complaint to case
- `POST /public-complaints/<id>/reject` — Reject complaint

## Frontend Notes

- The frontend is served from `Frontend/crms_frontend.html`
- It uses React, Tailwind CSS, Chart.js, and Framer Motion from CDNs.
- The UI is loaded from `/` and communicates with the Flask backend.
- reCAPTCHA is enabled in the frontend; the secret key must be configured in the backend environment.

## Security & Production

- Use a real `.env` file in production and never commit secrets.
- Use a production-ready WSGI server like Gunicorn instead of `python3 Backend/app.py`.
- Restrict `CORS_ORIGIN` to your trusted frontend host.
- Keep `RECAPTCHA_SECRET_KEY` secret.
- Use HTTPS in production.

## Troubleshooting

- If the backend cannot connect to MySQL, verify `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME`.
- If the frontend fails to load, make sure `Backend/app.py` is running and visit `http://localhost:5000`.
- To disable reCAPTCHA verification during local development, leave `RECAPTCHA_SECRET_KEY` empty.

## Notes

- `Backend/config.py` loads environment values and defaults.
- If `RECAPTCHA_SECRET_KEY` is missing, the backend allows requests to proceed for local testing.
- The frontend currently serves a single HTML file with embedded React code.
