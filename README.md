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
| Backend | Flask + Bcrypt (auth) |
| Database | MySQL 8 |
| Frontend | React 18 |
| API | REST (CORS enabled) |
| Data Format | JSON |
| Charts | Chart.js |
| Animations | Framer Motion |
| Styling | Tailwind CSS + Custom Glass UI |

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
python3 Backend/app.py
```

Expected output:

```bash
============================================================
  CRMS Flask API — Bengaluru Police Department
============================================================

[DB] Connection pool initialised → root@localhost:3306/crms

 * Running on http://0.0.0.0:5000
```

Once running, **open your browser** and visit:

```txt
http://localhost:5000
```

The frontend loads automatically and connects to the backend API.

---

# ✦ Runtime States

| Status | Meaning |
|---|---|
| 🟢 LIVE | Backend connected to real MySQL database |
| 🟠 DEMO | Running on local mock intelligence data |

---

# ✦ Core API Surface

## System Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | API liveness check |
| GET | `/stats` | Public case counts (landing page) |

---

## Cases (Inspector/Viewer)

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/cases` | Retrieve all cases + filters | Inspector/Viewer |
| GET | `/cases/<id>` | Single case lookup | Inspector/Viewer |
| GET | `/cases/<id>/officers` | Case + assigned officers | Inspector/Viewer |
| POST | `/cases` | Create investigation case | Inspector only |
| PATCH | `/cases/<id>` | Update case fields | Inspector only |
| DELETE | `/cases/<id>` | Hard delete case | Inspector only |

---

## Officers (Inspector/Viewer)

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/officers` | Officer roster + metrics | Inspector/Viewer |
| POST | `/officers` | Register officer | Inspector only |

---

## Case-Officer Assignments (Inspector only)

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/case-officer` | Case-officer mappings | Inspector/Viewer |
| POST | `/case-officer` | Assign officer to case | Inspector only |
| DELETE | `/case-officer` | Remove assignment | Inspector only |

---

## Analytics & Intelligence (Inspector/Viewer)

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/analytics` | Crime + status + location distribution | Inspector/Viewer |

---

## Authentication (Staff Portal)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/login` | Officer login (badge/name + password) |

---

## Public Complaints Review (Inspector only)

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/public-complaints` | List staging complaints | Inspector only |
| POST | `/public-complaints/<id>/promote` | Promote to full case | Inspector only |
| POST | `/public-complaints/<id>/reject` | Reject complaint | Inspector only |

---

## Public Portal (Citizens - No Auth)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/complaint` | Submit citizen complaint |
| POST | `/public/access-request` | Request case access |

---

# ✦ Intelligence Schema

```sql
cases
├── case_id                      (PK, AUTO_INCREMENT)
├── title                        (varchar)
├── description                  (text)
├── crime_type                   (enum: Cyber Fraud|Theft|Assault|Fraud|Other)
├── status                       (enum: Active|Solved|Closed)
├── location                     (varchar)
├── complaint_mode               (enum: Online|Offline)
├── complainant_name             (varchar, nullable)
├── complainant_contact          (varchar, nullable)
├── complainant_aadhaar          (varchar, last 4 digits only, nullable)
├── source                       (enum: officer|public)
├── date_reported                (timestamp)
└── last_updated                 (timestamp)

officers
├── officer_id                   (PK, AUTO_INCREMENT)
├── name                         (varchar)
├── rank                         (varchar)
├── badge                        (varchar, format: BPD-XXXX)
├── station                      (varchar)
├── phone                        (varchar)
├── email                        (varchar)
├── password_hash                (bcrypt, for login)
├── role                         (enum: inspector|viewer)
├── join_date                    (date)
└── active_cases / solved_cases  (computed via JOIN)

public_complaints               (STAGING TABLE FOR CITIZEN INTAKE)
├── complaint_id                 (PK, AUTO_INCREMENT)
├── complainant_name             (varchar)
├── contact                      (varchar)
├── email                        (varchar)
├── aadhaar_last4                (varchar, 4 digits)
├── crime_type                   (varchar)
├── location                     (varchar)
├── incident_desc                (text)
├── complaint_mode               (enum: Online|Offline)
├── status                       (enum: Pending|Promoted|Rejected)
├── submitted_at                 (timestamp)
├── reviewed_by                  (officer_id, nullable)
├── reviewed_at                  (timestamp, nullable)
├── promoted_case_id             (case_id reference, nullable)
└── (No PII stored — aadhaar limited to last 4 digits)

case_officer                    (JUNCTION TABLE)
├── case_id                      (FK → cases)
├── officer_id                   (FK → officers)
└── (Composite PK)
```

---

# ✦ User Roles & Permissions

## **Inspector (P1)** — Full Authority
- ✅ View all cases, officers, assignments, analytics
- ✅ Create new cases
- ✅ Update case details & status
- ✅ Assign/unassign officers
- ✅ Review & promote public complaints
- ✅ Delete cases (soft-close preferred)
- 🔐 Login with badge number (BPD-XXXX) or name + password

## **Viewer (P2)** — Read-Only
- ✅ View all cases, officers, assignments, analytics
- ❌ Cannot create/modify cases
- ❌ Cannot manage assignments
- ❌ Cannot review complaints
- 🔐 Login with badge/name + password

---

# ✦ Frontend ↔ Backend Flow

## **Staff Portal** (Officers)

| User Action | API Calls | Notes |
|---|---|---|
| Login | `POST /auth/login` | Badge/name + password; returns role |
| Dashboard boot | `GET /cases` + `GET /officers` | Loads operational data |
| Search cases | `GET /cases?status=...&crime_type=...&location=...&search=...` | Full-text search |
| View case detail | `GET /cases/<id>/officers` | Shows case + assigned officers |
| Create case | `POST /cases` | Inspector only; auto-increments BLR-XXX ID |
| Update case status | `PATCH /cases/<id>` | Inspector only; e.g., Active → Solved → Closed |
| Assign officer | `POST /case-officer` | Inspector only (UI missing - backend ready) |
| View assignments | `GET /case-officer` | Inspector/Viewer |
| View analytics | `GET /analytics` | Crime distribution, trends, officer workload |
| Review complaints | `GET /public-complaints?status=Pending` | Inspector only (UI missing - backend ready) |
| Promote complaint | `POST /public-complaints/<id>/promote` | Creates full case from staging complaint |
| Reject complaint | `POST /public-complaints/<id>/reject` | Marks as rejected |
| Logout | Frontend state clear | Session ends |

## **Public Portal** (Citizens - No Auth)

| Citizen Action | API Calls | Notes |
|---|---|---|
| Submit complaint | `POST /public/complaint` | Stores in `public_complaints` staging table; returns PC-XXX reference |
| Request access | `POST /public/access-request` | Logged to console (table ready for future) |
| View stats | `GET /stats` | Real-time case counts on landing page |
| *(UI missing)* | `GET /public-complaints/<id>` | Future: citizen tracking of their complaint |

---

# ✦ Key Workflows

## **Complaint Processing Pipeline**

```
┌──────────────────────────────────────────────────────────────┐
│ CITIZEN SUBMITS VIA PUBLIC PORTAL                           │
│ POST /public/complaint → stored in public_complaints         │
│ Reference: PC-001 (shown to citizen)                         │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ OFFICER REVIEWS IN STAFF DASHBOARD                          │
│ GET /public-complaints?status=Pending                        │
│ (UI NOT YET IMPLEMENTED)                                     │
└──────────────────────────────────────────────────────────────┘
                          ↓
                    ┌─────────────┐
                    │             │
              APPROVE         REJECT
                    │             │
                    ↓             ↓
        POST /promote      POST /reject
        public_complaints  public_complaints
        status=Promoted    status=Rejected
             ↓
        NEW FULL CASE
        cases.source='public'
        BLR-XXX format
```

## **Case Lifecycle**

```
CREATED (Active)
   ↓
   INVESTIGATION
   ↓
   SOLVED / CLOSED
   ↓
   ARCHIVED
```

---

# ✦ Reference IDs & Formatting

| Type | Format | Example | Storage |
|---|---|---|---|
| Case ID (Officer-filed) | BLR-XXX | BLR-001, BLR-042 | Integer PK, formatted for display |
| Complaint ID (Citizen-filed) | PC-XXX | PC-001, PC-015 | Auto-increment from `public_complaints` |
| Officer Badge | BPD-XXXX | BPD-7821, BPD-6543 | Unique identifier in officers table |

---

# ✦ Operational Notes

### Runtime Behavior
- Frontend gracefully falls back to mock data when backend is unreachable (🟠 DEMO mode).
- `PATCH status=Closed` is preferred over hard deletion (preserves history).
- Case IDs auto-increment; display ID is formatted as `BLR-{zeroPadded}`.
- Public complaints stored in staging table; never directly create cases.
- **Critical:** Passwords are bcrypt-hashed (12 rounds); never log or store plaintext.

### Missing Features (Roadmap)
- **Complaint Review UI:** Backend endpoints ready, frontend dashboard not yet implemented
- **Case-Officer Assignment UI:** Backend endpoints ready, frontend UI not yet implemented  
- **Pagination:** Large datasets (1000+ cases) need pagination to prevent performance issues
- **Citizen Case Tracking:** Citizens can submit complaints but cannot track status
- **Audit Trail:** No case modification history or change logs
- **Two-Factor Auth:** Basic login only; 2FA not implemented

### Production Deployment Checklist
- [ ] Use Gunicorn instead of Flask dev server
- [ ] Load credentials from environment variables (`.env` file)
- [ ] Add authentication middleware with JWT tokens
- [ ] Deploy behind HTTPS reverse proxy (nginx/Apache)
- [ ] Enable request rate limiting
- [ ] Set up database backups & recovery procedures
- [ ] Implement audit logging for sensitive operations
- [ ] Configure CORS whitelist (not `*`)
- [ ] Use connection pooling (already implemented in code)
- [ ] Monitor database query performance

---

<div align="center">

### CRMS · Bengaluru Police Department
#### Cyber Intelligence & Investigation Platform

</div>
