<div align="center">

# Themis's Domain — Crime Record Management System 🎯

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)  [![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)  [![Build Status](https://img.shields.io/badge/build-passing-success.svg)](#)

</div>

---

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Frontend](#frontend)
- [Security](#security)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)
- [Contact & Acknowledgements](#contact--acknowledgements)

---

## Overview
Themis's Domain is a **police investigation dashboard** built for the Bengaluru Police Department. It combines a Flask‑powered backend, a MySQL database, and an editorial‑styled single‑page React frontend. The system streamlines case management, citizen complaint intake, automated case assignment, and secure dossier delivery.

---

## Features ✨
- **Staff portal** – Role‑based login, full CRUD on cases, officer assignments, analytics, status updates.
- **Public portal** – Citizens file complaints, browse public cases, and request case‑dossier access (protected by reCAPTCHA + email OTP). The complaint form supports **one‑tap geolocation auto‑fill** for the incident address (with manual fallback).
- **Case discovery** – Search / filter by status, crime type, location, or keywords, with server‑side pagination.
- **Automated assignment** – Background scheduler promotes pending complaints to cases and auto‑assigns officers by severity and workload.
- **Access‑request workflow** – Authorized officers approve/reject citizen requests; approval triggers PDF dossier generation and email delivery (via Brevo HTTP API).
- **Editorial UI** – Magazine/newspaper‑inspired design (serif headlines, pull‑quote statistics, archival imagery).

---

## Architecture
Three logical layers:
1. **Backend (Flask)** – `Backend/` — REST API, authentication/sessions, business logic, background scheduler, PDF + email utilities.
2. **Database (MySQL)** – Officers, cases, complaints, access requests, sessions, evidence, timeline updates. Hosted on Aiven in production.
3. **Frontend (React via CDN)** – `Frontend/` — interactive SPA for staff and citizens, served by Flask at `/`.

```
Crime_DB/
├── Backend/
│   ├── app.py                  # Flask API — all routes, auth guards, validation
│   ├── queries.py              # all SQL (parameterized) + pagination helpers
│   ├── db_connection.py        # pooled MySQL connection
│   ├── assignment_algorithm.py # automated complaint → case assignment
│   ├── email_utils.py          # Brevo HTTP email + PDF dossier (mock fallback)
│   ├── otp_store.py            # in‑memory email OTP store (rate‑limited)
│   ├── config.py               # env‑driven config (.env)
│   ├── migrate_all.sql         # SINGLE consolidated migration (schema+indexes+seed)
│   └── test_*.py               # unit + security test suites
├── Frontend/
│   ├── src/                    # modular JSX + CSS sources (edit these)
│   ├── index.template.html     # HTML shell with __STYLES__ / __APP_JS__ slots
│   ├── build.py                # assembles src/ → crms_frontend.html
│   ├── crms_frontend.html      # GENERATED — do not edit by hand
│   └── README.md               # frontend build/workflow docs
├── scratch/                    # one‑off DB utilities (config‑driven, no secrets)
├── requirements.txt
├── Procfile                    # gunicorn entrypoint for Render
└── .env.example
```

---

## Installation 🚀
```bash
# Clone
git clone https://github.com/your-org/Crime_DB.git
cd Crime_DB

# Environment variables
cp .env.example .env
# Edit .env: MySQL credentials, reCAPTCHA keys, Brevo email (optional)

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Database Setup
A **single consolidated migration** creates the complete schema, all performance
indexes, the session table, and demo seed data:

```bash
mysql -u root -p < Backend/migrate_all.sql
```

For a managed host that disallows `CREATE DATABASE` / `USE` (e.g. Aiven free tier):
```bash
python3 scratch/migrate_to_aiven.py     # reads DB_* from .env
```

> Demo accounts use placeholder emails. To enable real email delivery, see the
> commented "OFFICER EMAIL OVERRIDES" block at the bottom of `migrate_all.sql`.

---

## Quick Start
```bash
python3 Backend/app.py
```
Open **http://localhost:5000**. The backend serves both the API and the frontend.

**Dev login:** Badge `BPD-7821`, password `crms1234` (inspector). Admin badge `ADM-0001`.

---

## API Reference 📚
All responses follow `{ "success": true, "data": … }` or `{ "success": false, "error": "…" }`.
List endpoints return a `pagination` block: `{ total_records, total_pages, current_page, limit }`.

Protected routes require the `X-Officer-Id` **and** `X-Session-Token` headers
(issued at login). Routes are guarded by role — see [Security](#security).

### Health & Stats
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | public | Health check |
| GET | `/stats` | public | Public landing statistics |

### Cases
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/cases`, `/api/cases` | officer | List cases (filters, pagination, visibility) |
| GET | `/cases/<id>` | officer | Case detail |
| POST | `/cases` | officer | Create case |
| PATCH | `/cases/<id>` | officer (admin for status) | Update case fields |
| DELETE | `/cases/<id>` | **admin** | Hard‑delete a case |
| GET | `/cases/<id>/officers` | officer | Officers on a case |
| GET | `/cases/<id>/highest-ranked` | officer | Highest‑ranked officer on a case |

### Timeline & Evidence
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET / POST | `/cases/<id>/updates` | officer (on case) | Case timeline (paginated) |
| GET / POST | `/cases/<id>/evidence` | officer (on case) | Evidence list / upload |
| GET | `/cases/evidence/file/<id>/<name>` | officer (on case) | Inline view |
| GET | `/cases/<id>/evidence/<name>/download` | officer (on case) | Download |
| DELETE | `/cases/evidence/<id>` | officer (admin/inspector/uploader) | Delete evidence |

### Officers & Assignments
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/officers` | officer | List officers (paginated) |
| POST | `/officers` | **admin** | Add officer |
| GET | `/officers/available?case_id=` | officer | Officers not on a case |
| GET | `/case-officer` | officer | Case‑officer pairings (paginated) |
| POST / DELETE | `/case-officer` | **admin** | Assign / unassign |
| POST | `/case-officer/add`, `/case-officer/remove` | **admin** | Reassign + email notify |

### Analytics & Assignment Engine
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/analytics` | officer | Dashboard analytics |
| GET | `/assignments/pending` | officer | Pending complaint queue (paginated) |
| POST | `/assignments/process` | **admin** | Trigger assignment algorithm |
| GET | `/admin/dashboard` | **admin** | Admin aggregate stats |
| GET | `/admin/cases` | **admin** | All cases (paginated) |
| GET/POST | `/admin/recommendations[...]` | **admin** | Assignment recommendation review |

### Public Portal (Citizens)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/public/cases` | Browse public cases (paginated) |
| POST | `/public/complaint` | Submit complaint (CAPTCHA + email OTP) |
| POST | `/public/access-request` | Request dossier access (CAPTCHA) |
| POST | `/public/verify-email`, `/public/otp/send`, `/public/otp/verify` | Email verification flow |

### Public Complaints Review (Staff)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/public-complaints` | officer | Review queue (paginated) |
| POST | `/public-complaints/<id>/promote` | **admin** | Promote to case |
| POST | `/public-complaints/<id>/reject` | **admin** | Reject complaint |

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Officer login (badge ID, password, reCAPTCHA); single‑device session |
| POST | `/auth/logout` | Revoke active session |

### Access Requests (Staff)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/access-requests` | officer | List (role‑filtered, paginated) |
| POST | `/api/access-requests/<id>/approve` | highest‑ranked/admin | Approve → emails PDF dossier |
| POST | `/api/access-requests/<id>/reject` | highest‑ranked/admin | Reject → notifies citizen |

---

## Frontend 🎨
The UI is **modular** under `Frontend/src/` and assembled by a small Python build
step into the single `crms_frontend.html` that Flask serves (React + Tailwind +
Framer Motion from CDNs — no bundler / no Node required on the server).

```bash
# After editing anything in Frontend/src/ or index.template.html:
python3 Frontend/build.py            # rebuild crms_frontend.html
python3 Frontend/build.py --check    # CI guard: fail if output is stale
```

> **Never edit `Frontend/crms_frontend.html` directly** — it's generated.
> See `Frontend/README.md` for the module layout and load order.

---

## Security 🔐
- **Passwords:** bcrypt hashing (cost 12).
- **Sessions:** random 64‑char tokens, single‑device enforcement, TTL + revocation.
  Protected routes require `X-Officer-Id` + `X-Session-Token`, validated per request.
- **Authorization:** role‑based guards — reads require a valid officer session;
  destructive/admin actions (create/delete case, manage officers/assignments,
  promote/reject complaints, run the assignment job) require the **admin** role.
- **Performance:** consolidated DB indexes back all common filter/sort paths;
  list endpoints are paginated with a hard page‑size cap.
- **Error hygiene:** internal exceptions are logged server‑side; clients receive
  generic messages (no stack/DB detail leakage).
- **Headers:** `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Cache-Control: no-store` on every response.
- **Input:** parameterized SQL throughout; file uploads restricted by extension +
  size with path‑traversal guards; reCAPTCHA on public forms.

**Before production:** rotate any credentials that were ever in plaintext, set
`CORS_ORIGIN` to your real frontend origin, use real reCAPTCHA keys, keep
`FLASK_DEBUG=false`, and serve over HTTPS.

---

## Testing 🧪
```bash
# From Backend/ (with the venv active)
python3 -m pytest -q
```
- `test_evidence_features.py` — upload validation, evidence access control, status‑update auth.
- `test_security_guards.py` — auth/role guards, session validation, error hygiene, security headers.

---

## Deployment
- **Hosting:** Render (free tier) via `Procfile` → `gunicorn Backend.app:app`.
- **Database:** Aiven managed MySQL (SSL).
- **Email:** Brevo HTTP API (Render free tier blocks outbound SMTP ports).
- Configure all of the above through environment variables in the Render dashboard.

---

## Contributing 🤝
1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/awesome-feature`).
3. Edit `Frontend/src/` (then `python3 Frontend/build.py`) and/or `Backend/`.
4. Ensure `pytest` passes and `python3 Frontend/build.py --check` is clean.
5. Submit a pull request with a clear description.

---

## License 📄
Licensed under the MIT License — see [LICENSE](LICENSE).

---

## Contact & Acknowledgements
- **Maintainer**: Venzz ([@venzz](https://github.com/venzz))
- **Thanks** to the Bengaluru Police Department for the domain context.
- **Special thanks** to the open‑source community for the libraries used.
