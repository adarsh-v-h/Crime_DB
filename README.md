<div align="center">

# Themis's Domain — Crime Record Management System

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENCE) [![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/) [![Build](https://img.shields.io/badge/build-passing-success.svg)](#)

**A police investigation dashboard for the Bengaluru Police Department.**  
Flask · MySQL · React · Deployed on Render + Aiven + Brevo.

</div>

---

## Table of Contents
1. [What it does](#what-it-does)
2. [Tech stack & accounts you need](#tech-stack--accounts-you-need)
3. [Local setup — step by step](#local-setup--step-by-step)
4. [Environment variables reference](#environment-variables-reference)
5. [Deploy to production](#deploy-to-production)
6. [Project structure](#project-structure)
7. [Frontend — editing & building](#frontend--editing--building)
8. [API reference](#api-reference)
9. [Performance optimizations](#performance-optimizations)
10. [Security](#security)
11. [Testing](#testing)
12. [Contributing](#contributing)
13. [License](#license)

---

## What it does

| Who | What they can do |
|-----|-----------------|
| **Citizens** | File complaints (reCAPTCHA + email OTP), browse public cases, request dossier access |
| **Officers (inspector)** | Log in, manage cases, upload evidence, add timeline updates, approve/reject access requests |
| **Admin** | Everything above + create officers, hard-delete cases, promote/reject complaints, trigger auto-assignment, view the geospatial operations map |

Key features:
- Role-based single-device login with session tokens
- Automated complaint → case assignment (background scheduler)
- PDF dossier generation + email delivery via Brevo
- Geolocation auto-fill on the complaint form
- Admin geospatial map (Leaflet + OpenStreetMap): police stations and case locations plotted across Bengaluru, with a permanent server-side geocode cache
- Editorial magazine-style UI (no bundler — React via CDN)
- Server-side pagination on every list endpoint
- Consolidated DB indexes on all filter/sort columns

---

## Tech stack & accounts you need

Before you start, create accounts on these free services:

| Service | What for | Sign up |
|---------|----------|---------|
| **GitHub** | Host the repo | github.com |
| **Render** | Host the Flask app (free tier) | render.com |
| **Aiven** | Managed MySQL database (free tier) | aiven.io |
| **Brevo** | Transactional email API (free tier, 300 emails/day) | brevo.com |
| **Google reCAPTCHA** | Protect public forms | google.com/recaptcha/admin |

> **Local dev only?** You only need a local MySQL install. Skip Aiven, Render, and Brevo — the app runs in offline mock mode for emails.

---

## Local setup — step by step

### 1. Prerequisites

```bash
# Required
python3 --version   # 3.10 or higher
mysql --version     # any recent MySQL 8.x

# Optional (only needed if you edit Frontend/src/)
python3 -m pip install --upgrade pip
```

### 2. Clone the repo

```bash
git clone https://github.com/adarsh-v-h/Crime_DB.git
cd Crime_DB
```

### 3. Python environment

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Create your `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_NAME=crms

# Use Google's public TEST keys for local dev (accept any token):
RECAPTCHA_SECRET_KEY=6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe
RECAPTCHA_PUBLIC_KEY=6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI
```

Everything else has sensible defaults — see [Environment variables reference](#environment-variables-reference).

### 5. Set up the database

One command creates the full schema, all indexes, and demo seed data:

```bash
mysql -u root -p < Backend/migrate_all.sql
```

> If your MySQL user isn't `root`, replace accordingly. The script creates the `crms` database automatically.

### 6. Run the app

```bash
python3 Backend/app.py
```

Open **http://localhost:5000** — Flask serves both the API and the frontend.

### 7. Log in

| Role | Badge | Password |
|------|-------|----------|
| Admin | `ADM-0001` | `crms1234` |
| Inspector | `BPD-7821` | `crms1234` |
| Inspector | `BPD-8912` | `crms1234` |

> Change these passwords before any real deployment.

### 8. (Optional) Enable real email locally

Leave `BREVO_API_KEY` empty and the app writes mock emails as JSON files to `Backend/mock_emails/` — useful for testing the email flow without a real account.

---

## Environment variables reference

Copy `.env.example` to `.env`. All variables with a default are optional.

### Database
| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DB_HOST` | ✅ | — | MySQL hostname |
| `DB_PORT` | ✅ | — | Usually `3306` |
| `DB_USER` | ✅ | — | MySQL username |
| `DB_PASSWORD` | ✅ | — | MySQL password |
| `DB_NAME` | ✅ | — | Database name (`crms`) |
| `DB_POOL_SIZE` | | `10` | Connections per process. Keep `workers × pool_size` under your DB's `max_connections`. Aiven free ≈ 20. |

### Flask
| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `FLASK_HOST` | | `0.0.0.0` | |
| `FLASK_PORT` | | `5000` | Render sets `PORT` automatically |
| `FLASK_DEBUG` | | `false` | Never `true` in production |

### CORS
| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `CORS_ORIGIN` | | `*` | Set to your exact frontend URL in production |

### Auth & scheduler
| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `AUTH_SESSION_TTL_HOURS` | | `12` | How long a login session lasts |
| `ENABLE_ASSIGNMENT_SCHEDULER` | | `true` | Set `false` to disable the background job |
| `ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS` | | `60` | How often the scheduler runs |

### reCAPTCHA
| Variable | Required | Notes |
|----------|----------|-------|
| `RECAPTCHA_SECRET_KEY` | ✅ | Get from [google.com/recaptcha/admin](https://google.com/recaptcha/admin). Use test keys locally. |
| `RECAPTCHA_PUBLIC_KEY` | ✅ | Embedded in the frontend |

### Brevo email
| Variable | Required | Notes |
|----------|----------|-------|
| `BREVO_API_KEY` | | Leave empty → offline mock mode |
| `BREVO_FROM_EMAIL` | | Must be verified in your Brevo account |
| `BREVO_FROM_NAME` | | Display name for outgoing emails |

---

## Deploy to production

### Step 1 — Aiven (database)

1. Sign up at **aiven.io** → create a free **MySQL** service.
2. Once running, copy the connection details from the Aiven console:
   - Host, Port, User, Password, Database name (`defaultdb` on free tier).
3. Run the migration against Aiven (reads from your `.env`):
   ```bash
   # Set DB_* in .env to your Aiven values first
   python3 scratch/migrate_to_aiven.py
   ```
4. To set real officer emails (so notifications actually land in inboxes), uncomment and edit the `OFFICER EMAIL OVERRIDES` block at the bottom of `Backend/migrate_all.sql`, then run those `UPDATE` statements manually.

### Step 2 — Brevo (email)

1. Sign up at **brevo.com** → go to **SMTP & API → API Keys** → create a key.
2. Go to **Senders & IPs → Senders** → add and verify your sender email address.
3. Copy the API key — you'll add it to Render in the next step.

### Step 3 — Google reCAPTCHA

1. Go to **[google.com/recaptcha/admin](https://www.google.com/recaptcha/admin)**.
2. Register a new site → choose **reCAPTCHA v2 "I'm not a robot"** (or Invisible).
3. Add your Render domain (e.g. `your-app.onrender.com`) to the allowed domains.
4. Copy the **Site Key** (public) and **Secret Key** (private).

### Step 4 — Render (hosting)

1. Sign up at **render.com** → **New → Web Service** → connect your GitHub repo.
2. Settings:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn Backend.app:app`
   - (The `Procfile` already sets this — Render picks it up automatically.)
3. Under **Environment**, add every variable from your `.env`:

   ```
   DB_HOST          → your Aiven host
   DB_PORT          → your Aiven port
   DB_USER          → avnadmin (or your Aiven user)
   DB_PASSWORD      → your Aiven password
   DB_NAME          → defaultdb
   DB_POOL_SIZE     → 10
   FLASK_DEBUG      → false
   CORS_ORIGIN      → https://your-app.onrender.com
   RECAPTCHA_SECRET_KEY  → your real secret key
   RECAPTCHA_PUBLIC_KEY  → your real site key
   BREVO_API_KEY    → your Brevo API key
   BREVO_FROM_EMAIL → your verified sender email
   BREVO_FROM_NAME  → Bengaluru Police Themis's Domain Team
   AUTH_SESSION_TTL_HOURS → 12
   ENABLE_ASSIGNMENT_SCHEDULER → true
   ```

4. Click **Deploy**. Render builds and starts the app. Your URL is `https://your-app.onrender.com`.

> **Free tier note:** Render spins down after 15 minutes of inactivity. The first request after sleep takes ~30 seconds. Upgrade to a paid plan to avoid this.

### Step 5 — Update reCAPTCHA domain

Go back to your reCAPTCHA admin console and confirm your Render domain is in the allowed list.

---

## Project structure

```
Crime_DB/
├── Backend/
│   ├── app.py                  # Flask API — all routes, auth guards, validation
│   ├── queries.py              # all SQL (explicit columns, parameterized, paginated)
│   ├── db_connection.py        # pooled MySQL connection (env-configurable size)
│   ├── assignment_algorithm.py # automated complaint → case assignment
│   ├── email_utils.py          # Brevo HTTP email + PDF dossier (mock fallback)
│   ├── otp_store.py            # in-memory email OTP store (rate-limited)
│   ├── geocode.py              # server-side geocoding + DB cache (admin map)
│   ├── config.py               # env-driven config
│   ├── migrate_all.sql         # single consolidated migration (schema+indexes+seed)
│   ├── test_evidence_features.py
│   └── test_security_guards.py
├── Frontend/
│   ├── src/                    # modular JSX + CSS sources — edit these
│   │   ├── 00-config.jsx       # API base, auth helpers, apiFetch
│   │   ├── 01-icons.jsx
│   │   ├── 02-shared.jsx       # shared components + style constants
│   │   ├── 03-layout.jsx       # page shell + masthead
│   │   ├── 04-LandingPage.jsx
│   │   ├── 05-PublicPortal.jsx # complaint form, browse, access request
│   │   ├── 06-StaffDashboard.jsx
│   │   ├── 07-AdminDashboard.jsx
│   │   ├── 08-LoginPage.jsx
│   │   ├── 09-App.jsx
│   │   └── styles.css
│   ├── index.template.html     # HTML shell with __STYLES__ / __APP_JS__ slots
│   ├── build.py                # assembles src/ → crms_frontend.html
│   ├── crms_frontend.html      # GENERATED — do not edit by hand
│   └── README.md
├── scratch/
│   ├── migrate_to_aiven.py     # apply migrate_all.sql to a managed host
│   ├── migrate_indexes.py      # idempotent index applier (--dry-run supported)
│   └── test_conn.py            # quick DB connectivity check
├── .env.example
├── .gitignore
├── Procfile
└── requirements.txt
```

---

## Frontend — editing & building

The UI is modular under `Frontend/src/`. A Python build step assembles the modules into the single `crms_frontend.html` that Flask serves. No Node, no bundler.

```bash
# After editing any file in Frontend/src/:
python3 Frontend/build.py

# CI guard — fails if the generated file is stale:
python3 Frontend/build.py --check
```

> **Never edit `Frontend/crms_frontend.html` directly.** It is regenerated from `src/` and your changes will be overwritten.

The browser always receives the single assembled file — same performance as before modularization.

---

## API reference

All responses: `{ "success": true/false, "data": …, "error": "…" }`.  
List endpoints also return `"pagination": { total_records, total_pages, current_page, limit }`.  
Protected routes require headers: `X-Officer-Id: <id>` and `X-Session-Token: <token>` (issued at login).

### Public (no auth)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves the frontend |
| GET | `/health` | Health check |
| GET | `/stats` | Landing page statistics |
| GET | `/public/cases` | Browse cases (paginated, filterable) |
| POST | `/public/verify-email` | Validate email domain (MX check) |
| POST | `/public/otp/send` | Send OTP to email |
| POST | `/public/otp/verify` | Verify OTP → returns token |
| POST | `/public/complaint` | Submit complaint (CAPTCHA + OTP token) |
| POST | `/public/access-request` | Request case dossier access (CAPTCHA) |

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Login with badge + password + CAPTCHA |
| POST | `/auth/logout` | Revoke session |

### Cases — officer
| Method | Path | Notes |
|--------|------|-------|
| GET | `/cases`, `/api/cases` | Filtered, paginated, visibility-scoped |
| GET | `/cases/<id>` | Case detail |
| POST | `/cases` | Create case |
| PATCH | `/cases/<id>` | Update fields (status change = admin only) |
| DELETE | `/cases/<id>` | Hard delete — **admin only** |
| GET | `/cases/<id>/officers` | Assigned officers |
| GET | `/cases/<id>/highest-ranked` | Highest-ranked officer on case |
| GET/POST | `/cases/<id>/updates` | Timeline (paginated) |
| GET/POST | `/cases/<id>/evidence` | Evidence list / upload |
| GET | `/cases/evidence/file/<id>/<name>` | Inline file view |
| GET | `/cases/<id>/evidence/<name>/download` | Download |
| DELETE | `/cases/evidence/<id>` | Delete evidence |
| POST | `/cases/<id>/request-dossier` | Email dossier to self |

### Officers & assignments — officer/admin
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/officers` | officer | Paginated |
| POST | `/officers` | **admin** | Create officer |
| GET | `/officers/available?case_id=` | officer | Officers not on a case |
| GET | `/case-officer` | officer | All pairings (paginated) |
| POST/DELETE | `/case-officer` | **admin** | Assign / unassign |
| POST | `/case-officer/add` | **admin** | Add + email notify |
| POST | `/case-officer/remove` | **admin** | Remove + email notify |

### Admin
| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/dashboard` | Aggregate stats |
| GET | `/admin/cases` | All cases (paginated) |
| GET | `/admin/map-data` | Stations + case locations with cached coordinates for the map |
| GET | `/analytics` | Charts data |
| GET | `/assignments/pending` | Pending complaint queue |
| POST | `/assignments/process` | Trigger auto-assignment |
| GET | `/public-complaints` | Complaint review queue |
| POST | `/public-complaints/<id>/promote` | Promote to case |
| POST | `/public-complaints/<id>/reject` | Reject |
| GET | `/api/access-requests` | Access request list |
| POST | `/api/access-requests/<id>/approve` | Approve → email PDF |
| POST | `/api/access-requests/<id>/reject` | Reject → notify |
| GET/POST | `/admin/recommendations[...]` | Assignment recommendation review |

---

## Performance optimizations

The following optimizations have been applied to keep the app fast under load:

### 1. Connection pooling
`db_connection.py` uses `mysql.connector.pooling.MySQLConnectionPool`. Pool size is configurable via `DB_POOL_SIZE` (default 10, clamped 1–32). The pool is initialized once at startup and shared across all requests in a process.

```
Total DB connections = (Gunicorn workers) × DB_POOL_SIZE
Keep this under your DB's max_connections (Aiven free ≈ 20).
```

### 2. JOIN queries instead of multiple round-trips
All multi-table reads use a single JOIN query rather than separate queries per record. Examples:
- Case lists fetch assigned officer IDs in the same query via `GROUP_CONCAT`.
- Officer workload counts use a single conditional aggregate (`SUM(status = 'Active')`) instead of two `COUNT(*)` queries.
- `/case-officer/add` and `/case-officer/remove` use the existing join-based helpers.

### 3. Explicit column selection — no `SELECT *`
Every query selects only the columns its consumers actually read. `SELECT *` has been eliminated across `queries.py` and `assignment_algorithm.py`. Benefits:
- Less data transferred over the network from Aiven.
- Smaller result sets to deserialize.
- Queries are stable against future schema additions.

### 4. Database indexes
All common filter and sort columns are indexed. Applied via `Backend/migrate_all.sql` (inline with each table) and idempotently via `scratch/migrate_indexes.py`.

| Table | Index | Backs |
|-------|-------|-------|
| `cases` | `(status, date_reported)` | Status filter + date sort |
| `cases` | `(crime_type)` | Crime type filter + analytics |
| `cases` | `(date_reported)` | Unfiltered sort + 6-month range |
| `officers` | `(badge)`, `(name)`, `(role)` | Login lookup, admin lookup |
| `public_complaints` | `(status, submitted_at)` | Pending queue filter + sort |
| `case_access_requests` | `(requested_at)` | Requests list sort |
| `case_updates` | `(case_id, created_at)` | Timeline per case |
| `case_evidence` | `(case_id, created_at)` | Evidence per case |

### 5. Server-side pagination
Every list endpoint accepts `?page=` and `?limit=` (default 25, max 100). The DB returns only the requested page — no full-table loads.

### 6. Modular frontend — no runtime cost
The frontend source is split into 10 modules under `Frontend/src/` for maintainability, but `build.py` assembles them into a single file before serving. The browser receives the same single file as before — zero performance difference.

### 7. Server-side geocode cache (admin map)
The admin map plots police stations and case locations across Bengaluru. Place
names (even vague ones like "JP Nagar") are resolved to coordinates **once** by
the backend (`geocode.py`) via OpenStreetMap Nominatim, then stored permanently
in the `geocode_cache` table — shared across all admins and browsers.

- `/admin/map-data` returns coordinates straight from the DB cache, so the map
  renders **instantly** after the first warm-up.
- Never-seen places are geocoded in a **background thread**; the response reports
  a `pending` count and the client polls briefly to pick up new coordinates.
- Confirmed-unresolvable names (e.g. org units like "Cyber Crime Division") are
  cached as misses so they're never retried.
- Map tiles, the Leaflet library, and (formerly) geocoding all run client-side or
  are cached — nothing here depends on Render's blocked outbound SMTP ports.

---

## Docker (optional)

The project ships a `Dockerfile` and `docker-compose.yml` for one-command local
setup — handy if you don't want to install Python/MySQL on your machine.

```bash
# Build + run the app and a MySQL container together:
docker compose up --build
# App: http://localhost:5000   (migration runs automatically on first boot)
```

> Docker is **optional**. Production on Render does **not** use it — Render builds
> from the `Procfile`/`requirements.txt` directly. Docker is purely a convenience
> for local development and for hosts that expect a container image.

## Security

- **Passwords:** bcrypt (cost 12).
- **Sessions:** random 64-char tokens, single-device enforcement, TTL + revocation. Every protected request validates `X-Officer-Id` + `X-Session-Token`.
- **Authorization:** role guards on every route — reads require a valid officer session; writes/admin actions require the `admin` role (server-enforced, not just client-side).
- **Error hygiene:** exceptions logged server-side; clients receive generic messages — no stack traces or DB details leak.
- **HTTP headers:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` on every response.
- **Input:** parameterized SQL everywhere; file uploads restricted by extension + size with path-traversal guards; reCAPTCHA on all public forms; email OTP on complaint submission.
- **CORS:** origin is env-driven — set `CORS_ORIGIN` to your exact frontend URL in production.

---

## Testing

```bash
# From the project root, with venv active:
cd Backend
python3 -m pytest -q
```

| File | What it tests |
|------|---------------|
| `test_evidence_features.py` | Upload validation, evidence access control, status-update auth |
| `test_security_guards.py` | Auth/role guards, session validation, error hygiene, security headers |

Both suites mock the database layer — no live DB needed to run them.

---

## Contributing

1. Fork the repo and create a feature branch.
2. Edit `Frontend/src/` for UI changes, then run `python3 Frontend/build.py`.
3. Edit `Backend/` for API/logic changes.
4. Run `python3 -m pytest -q` (all tests must pass).
5. Run `python3 Frontend/build.py --check` (generated file must be up to date).
6. Open a pull request with a clear description of what changed and why.

---

## License

MIT — see [LICENCE](LICENCE).

---

## Contact & Acknowledgements

- **Maintainer:** Venzz ([@adarsh-v-h](https://github.com/adarsh-v-h))
- Built with Flask, MySQL, React, Tailwind CSS, Framer Motion, ReportLab, Brevo, and the Unsplash image library.
