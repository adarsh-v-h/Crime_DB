<div align="center">

# ⚡ CRMS
### Crime Record Management System

#### Bengaluru Police Department · Cyber Intelligence Platform

<img src="https://img.shields.io/badge/STATUS-LIVE-22c55e?style=for-the-badge">
<img src="https://img.shields.io/badge/STACK-FLASK%20%7C%20MYSQL%20%7C%20REACT-6366f1?style=for-the-badge">
<img src="https://img.shields.io/badge/UI-CINEMATIC%20DASHBOARD-06b6d4?style=for-the-badge">

---

### Futuristic cybercrime intelligence platform for case tracking, officer coordination, and operational analytics.

</div>

---

# ✦ System Overview

CRMS is a modern crime intelligence and investigation platform designed for urban law enforcement environments like Bengaluru.

The system combines:

- Cybercrime tracking
- Case lifecycle management
- Officer assignment workflows
- Intelligence analytics
- Real-time operational dashboards

into a unified investigation ecosystem.

---

# ✦ Architecture

```txt
crms_backend/
├── app.py              → Flask API entrypoint
├── queries.py          → SQL operations layer
├── db_connection.py    → MySQL connection pool
├── config.py           → Environment + credentials
├── setup_db.sql        → Schema + seed data
├── requirements.txt    → Python dependencies
└── crms_frontend.html  → Cinematic frontend UI
```

---

# ✦ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask |
| Database | MySQL 8 |
| Frontend | React / HTML |
| API | REST |
| Data Format | JSON |
| Charts | Recharts |
| Styling | Tailwind / Custom UI |

---

# ✦ Quick Start

## 1 ▸ Database Setup

```bash
mysql -u root -p < setup_db.sql
```

This initializes:

- `crms` database
- all schema tables
- seed officers
- seeded case intelligence data
- assignment relationships

---

## 2 ▸ Configure Credentials

Open:

```python
config.py
```

Update:

```python
DB_PASSWORD = "your_mysql_password_here"
```

---

## 3 ▸ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4 ▸ Launch Backend

```bash
python app.py
```

Expected output:

```bash
============================================================
  CRMS Flask API — Bengaluru Police Department
============================================================

[DB] Connection pool initialised → root@localhost:3306/crms

 * Running on http://0.0.0.0:5000
```

---

## 5 ▸ Open Frontend

Launch:

```bash
crms_frontend.html
```

The frontend automatically connects to:

```txt
http://localhost:5000
```

---

# ✦ Runtime States

| Status | Meaning |
|---|---|
| 🟢 LIVE | Backend connected to real MySQL database |
| 🟠 DEMO | Running on local mock intelligence data |

---

# ✦ Core API Surface

# Cases

| Method | Endpoint | Description |
|---|---|---|
| GET | `/cases` | Retrieve all cases + filters |
| GET | `/cases/<id>` | Single case lookup |
| POST | `/cases` | Create investigation case |
| PATCH | `/cases/<id>` | Update case fields |
| DELETE | `/cases/<id>` | Hard delete case |
| GET | `/cases/<id>/officers` | Hydrated officer intelligence |

---

# Officers

| Method | Endpoint | Description |
|---|---|---|
| GET | `/officers` | Officer roster + metrics |
| POST | `/officers` | Register officer |

---

# Assignments

| Method | Endpoint | Description |
|---|---|---|
| GET | `/case-officer` | Case-officer mappings |
| POST | `/case-officer` | Assign officer to case |
| DELETE | `/case-officer` | Remove assignment |

---

# Analytics

| Method | Endpoint | Description |
|---|---|---|
| GET | `/analytics` | Crime distribution + trends |

---

# Public Portal

| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/complaint` | Citizen complaint intake |
| POST | `/public/access-request` | Request case access |

---

# ✦ Intelligence Schema

```sql
cases
├── case_id
├── title
├── description
├── crime_type
├── status
├── date_reported
├── location
├── complaint_mode
└── last_updated

officers
├── officer_id
├── name
├── rank
├── badge
├── station
├── phone
├── email
└── join_date

case_officer
├── case_id
└── officer_id
```

---

# ✦ Frontend ↔ Backend Flow

| Frontend Action | API Mapping |
|---|---|
| Dashboard boot | `GET /cases` + `GET /officers` |
| Search intelligence | `GET /cases?...` |
| Register case | `POST /cases` |
| Update status | `PATCH /cases/:id` |
| Close investigation | `PATCH status=Closed` |
| Public complaint | `POST /public/complaint` |
| Access request | `POST /public/access-request` |

---

# ✦ Operational Notes

- Frontend gracefully falls back to mock data when backend is unavailable.
- `PATCH status=Closed` is preferred over destructive deletion.
- `case_id_display` uses `BLR-XXX` tactical formatting.
- Production deployment should use:
  - Gunicorn
  - environment variables
  - auth middleware
  - HTTPS reverse proxy

---

<div align="center">

### CRMS · Bengaluru Police Department
#### Cyber Intelligence & Investigation Platform

</div>
