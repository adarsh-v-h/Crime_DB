# CRMS — Remaining Work & Bug Fix Status

**Last updated:** 2026-05-24  
**Reference blueprint:** [`crms_remaining_work_and_bugfix_blueprint.md`](./crms_remaining_work_and_bugfix_blueprint.md)

This document maps the blueprint to what the codebase **actually implements** (citizen **case access requests**, not a separate `assignment_requests` table) and records what was fixed in this pass versus what is still open.

---

## Terminology note (blueprint vs code)

| Blueprint term | Actual implementation |
|----------------|----------------------|
| `assignment_requests` table | **`case_access_requests`** (`migrate_v3.sql`) |
| `GET /assignment-requests` | **`GET /api/access-requests`** |
| `POST .../approve` / `reject` | **`POST /api/access-requests/<id>/approve`** and **`/reject`** |
| Officer approves case **assignment** | Officer approves citizen **dossier access** for cases they handle |

The operational workflow is: **citizen submits access request → assigned officer (or admin/inspector) approves/declines → email + PDF (if approved)**.

---

## Bugs fixed in this pass

### 1. Missing staff UI for access requests (CRITICAL)

**Problem:** The staff dashboard had an “ACCESS REQUESTS” tab and backend wiring (`loadAccessRequests`, `handleDecide`), but **no JSX** for `activeSubTab === "requests"`. The dossiers block also had a broken fragment (`</div>` instead of `</>`), which could break rendering.

**Fix:** Added a full **Access Requests** panel with list, status badges, approve/decline actions, loading and error states, and success feedback. Corrected dossiers fragment closing.

**Files:** `Frontend/crms_frontend.html`

### 2. Missing authorization on approve/reject (CRITICAL)

**Problem:** Any logged-in officer could approve or reject any pending request, even for cases they were not assigned to.

**Fix:**

- `queries.officer_is_assigned_to_case(officer_id, case_id)`
- `_officer_may_decide_access_request()` in `app.py` — **admin** and **inspector** bypass; others must be on `case_officer` for that case
- Approve/reject return **403** when unauthorized

**Files:** `Backend/queries.py`, `Backend/app.py`

### 3. Race / double-processing on status update (HIGH)

**Problem:** `update_access_request_status` could overwrite an already-processed request.

**Fix:** `UPDATE ... WHERE request_id = %s AND status = 'Pending'`; endpoint returns **400** if no row updated.

**Files:** `Backend/queries.py`, `Backend/app.py`

---

## Already working (no change required)

| Area | Status |
|------|--------|
| Public submit access request | `POST /public/access-request` + reCAPTCHA |
| List requests (role visibility) | `GET /api/access-requests` — assigned cases only; admin/inspector see all |
| Approve + email/PDF async | `email_utils.send_decision_email_async` + mock fallback |
| Reject + notification async | Same engine, no PDF attachment |
| Query layer for access requests | `submit_case_access_request`, `get_case_access_requests`, `get_access_request_by_id`, `update_access_request_status` |
| DB schema | `case_access_requests` in `migrate_v3.sql` |
| `.env` in `.gitignore` | Present (rotate secrets if ever committed historically) |

---

## Remaining work (from blueprint, adapted)

### Phase 1 — Security (partially done)

| Task | Status |
|------|--------|
| Ownership validation on approve/reject | **Done** |
| Role guards on access-request decisions | **Done** (admin/inspector vs assigned) |
| Central `@require_role` decorators | **Not done** — permissions still scattered in routes |
| JWT instead of `X-Officer-Id` header | **Not done** — blueprint recommendation |
| Rotate SMTP/CAPTCHA/DB secrets if exposed | **Manual** — verify repo history |

### Phase 2 — Database

| Task | Status |
|------|--------|
| `case_access_requests` table | **Done** (`migrate_v3.sql`) |
| Separate `assignment_requests` table | **N/A** — not part of current design |
| Ordered `migrations/001_*.sql` layout | **Not done** — still `setup_db.sql`, `migrate_v2.sql`, `migrate_v3.sql` |
| Document migration run order in README | **Recommended** |

### Phase 3 — API layer

| Task | Status |
|------|--------|
| Access request CRUD/list/approve/reject | **Done** |
| Blueprint’s `/assignment-requests` routes | **N/A** — use `/api/access-requests` |

### Phase 4 — Frontend

| Task | Status |
|------|--------|
| Access Requests tab + cards + approve/reject | **Done** (this pass) |
| Toast library (vs inline banners) | **Optional** — currently inline success/error |
| Auto-refresh polling | **Not done** — manual refresh on tab load / after action |
| Optimistic UI updates | **Not done** — reloads list after decision |

### Phase 5 — Email

| Task | Status |
|------|--------|
| Approval email + PDF | **Done** |
| Rejection email | **Done** |
| Async via daemon thread | **Done** |
| Officer notification on new request | **Not done** |
| `send_assignment_*` helpers from blueprint | **N/A** — use `send_decision_email` |

### Phase 6 — Polish & architecture

| Task | Status |
|------|--------|
| Pending/accepted/rejected badges in UI | **Done** |
| Skeleton loaders | **Partial** — spinner only |
| Analytics counters for pending requests | **Not done** |
| `assignment_audit_logs` table | **Not done** |
| WebSocket live updates | **Not done** |
| Flask-Migrate / Alembic | **Not done** |

---

## Public complaints workflow (related, separate)

The blueprint also mentions public complaints and automated assignment. These exist separately:

- `POST /public/complaint`, scheduler in `assignment_algorithm.py`
- Staff promotion/rejection routes under `/public-complaints/...`

They are **not** the same as case access requests. No changes were made there in this pass.

---

## How to verify locally

1. **Database:** Run migrations in order: `setup_db.sql` → `migrate_v2.sql` → `migrate_v3.sql`
2. **Backend:** `cd Backend && python app.py`
3. **Frontend:** Open `Frontend/crms_frontend.html` (API base `http://localhost:5000`)
4. **Staff flow:** Log in as an officer assigned to case `BLR-001` (seed data). Open **ACCESS REQUESTS**, approve/decline pending row.
5. **Email:** Without SMTP in `.env`, check `Backend/mock_emails/` for JSON logs and PDF on approve.

---

## Suggested next implementation order

1. Centralize auth helpers (`require_officer`, `require_role`) without changing response shapes existing clients rely on.
2. README section: migration order + env vars (`SMTP_*`, `RECAPTCHA_*`).
3. Optional: poll `GET /api/access-requests` every 30s on requests tab.
4. Optional: audit log table for approve/reject actions.
5. Long-term: JWT sessions (blueprint recommendation).

---

## Files touched in bug-fix pass

- `Backend/app.py` — authorization helpers; stricter approve/reject
- `Backend/queries.py` — `officer_is_assigned_to_case`; pending-only update
- `Frontend/crms_frontend.html` — Access Requests panel; JSX fix

---

## Final verdict

The previous AI left the **backend and email engine largely complete** but stopped before the **staff access-request UI** and **approve/reject authorization**. Those gaps are now closed for the **case access request** workflow described in the real schema—not the blueprint’s hypothetical `assignment_requests` API.

Remaining items are mostly **hardening, polish, and architectural upgrades** from the blueprint, not blockers for the core approve/decline + notify citizen flow.
