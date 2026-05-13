# CRMS — Crime Record Management System
## Bengaluru Police Department · Backend Setup Guide

---

## Project Structure

```
crms_backend/
├── app.py              ← Flask entry point — all API routes
├── queries.py          ← All SQL operations (no SQL in app.py)
├── db_connection.py    ← MySQL connection pool
├── config.py           ← Database credentials & server settings
├── setup_db.sql        ← One-time schema creation + seed data
├── requirements.txt    ← Python dependencies
└── crms_frontend.html  ← Frontend (UI unchanged, now API-wired)
```

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python      | 3.9+    |
| MySQL       | 8.0+    |
| pip         | any     |

---

## Step 1 — Set Up the Database

Open MySQL and run the setup script:

```bash
mysql -u root -p < setup_db.sql
```

This creates the `crms` database, all three tables, and seeds 10 cases + 7 officers + all assignments.

---

## Step 2 — Configure Credentials

Open `config.py` and set your MySQL password:

```python
DB_PASSWORD = "your_mysql_password_here"
```

Everything else can stay as-is for local development.

---

## Step 3 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4 — Run the Backend

```bash
python app.py
```

You should see:

```
============================================================
  CRMS Flask API — Bengaluru Police Department
============================================================
[DB] Connection pool initialised → root@localhost:3306/crms
 * Running on http://0.0.0.0:5000
```

---

## Step 5 — Open the Frontend

Open `crms_frontend.html` directly in your browser. The page auto-connects to `http://localhost:5000`.

- **Green "Live" dot** in the top bar = API connected, real MySQL data
- **Amber "Demo" dot** = API not reachable, running on built-in mock data (UI still fully functional)

---

## API Endpoints

### Cases

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cases` | All cases. Filters: `?status=Active&crime_type=Cyber+Fraud&search=korama` |
| GET | `/cases/<id>` | Single case by integer ID |
| POST | `/cases` | Create new case |
| PATCH | `/cases/<id>` | Update case fields (e.g. `{"status": "Solved"}`) |
| DELETE | `/cases/<id>` | Hard delete (prefer PATCH status=Closed) |
| GET | `/cases/<id>/officers` | Case detail with hydrated officer objects |

### Officers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/officers` | All officers with computed active/solved counts |
| POST | `/officers` | Add new officer |

### Assignments (case_officer)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/case-officer` | All assignments (JOIN across all 3 tables) |
| POST | `/case-officer` | Assign officer to case: `{"case_id": 1, "officer_id": 3}` |
| DELETE | `/case-officer` | Remove assignment |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics` | Crime dist, status dist, monthly trends, location dist |

### Public Portal

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/public/complaint` | Citizen complaint — inserts into cases as Active |
| POST | `/public/access-request` | Case access request (logged, not stored in MVP) |

### Health

| Method | Endpoint |
|--------|----------|
| GET | `/health` |

---

## Error Response Format

All errors return:
```json
{ "success": false, "error": "Human-readable message" }
```

With appropriate HTTP status codes: 400 (validation), 404 (not found), 500 (DB error).

---

## Frontend ↔ Backend Mapping

| Frontend Action | API Call |
|----------------|----------|
| Staff dashboard load | GET /cases + GET /officers |
| Search / filter cases | GET /cases?status=&crime_type=&search= |
| Click "New Case" → submit | POST /cases |
| Change status dropdown in case modal | PATCH /cases/:id |
| Click trash icon on case | PATCH /cases/:id { status: "Closed" } |
| Assignments tab load | Built from local cases+officers state (or GET /case-officer) |
| Analytics charts | Local aggregation over cases state |
| Public complaint submit | POST /public/complaint |
| Public access request submit | POST /public/access-request |

---

## Database Schema

```sql
cases          (case_id PK, title, description, crime_type, status ENUM,
                date_reported, location, complaint_mode ENUM, last_updated)

officers       (officer_id PK, name, rank, badge, station, phone, email, join_date)

case_officer   (case_id FK, officer_id FK)   ← M:M junction
```

---

## Notes

- The frontend falls back to mock data silently if the backend is unreachable — useful for demos without a running server.
- `handleDeleteCase` maps to `PATCH status=Closed` (not a hard DELETE) to preserve case history, matching the schema design doc.
- The `case_id_display` field (BLR-XXX format) is computed by the backend and sent alongside the integer `case_id`. The frontend uses the display string for rendering.
- For production: add authentication middleware, replace `FLASK_DEBUG=True`, use Gunicorn, and store credentials in environment variables rather than config.py.
