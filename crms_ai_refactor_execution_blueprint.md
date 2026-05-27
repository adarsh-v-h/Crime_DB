# CRMS Refactor Execution Blueprint

Repository analyzed from uploaded Repomix export. fileciteturn0file0

---

# Core Strategic Direction

The current CRMS architecture is actually in a good state for staged AI-assisted refactoring.

The biggest danger is NOT code complexity.
The biggest danger is:

- breaking existing API contracts
- breaking frontend fetch calls
- corrupting assignment flow
- introducing schema mismatch
- AI rewriting large files unnecessarily
- AI touching UI styling accidentally
- AI renaming fields/functions/endpoints

The solution is:

- small isolated migrations
- backend-first sequence
- schema stabilization before UI
- additive changes first
- destructive changes only at the end
- strict prompt boundaries

This document gives the safest implementation order for Claude Code / Antigravity / Cursor / Gemini CLI style coding agents.

---

# HIGH RISK FILES

These files are central nervous system files.
AI should modify them carefully and minimally.

## Backend

- Backend/app.py
- Backend/queries.py
- Backend/assignment_algorithm.py
- Backend/email_utils.py
- Backend/setup_db.sql
- Backend/migrate_v2.sql
- Backend/migrate_v3.sql

## Frontend

- Frontend/crms_frontend.html

---

# ABSOLUTE GLOBAL RULES FOR ALL AI TASKS

Use these rules in EVERY prompt.

```text
CRITICAL RULES:

1. DO NOT redesign the UI.
2. DO NOT change fonts, spacing system, colors, animations, shadows, layout language, or visual identity.
3. DO NOT rename existing APIs.
4. DO NOT rename existing JSON response fields.
5. DO NOT remove existing endpoints.
6. DO NOT rewrite entire files.
7. ONLY patch the minimum necessary code.
8. Preserve all existing fetch() calls unless explicitly instructed.
9. Preserve all existing role logic unless explicitly instructed.
10. Maintain backward compatibility.
11. Do not touch unrelated components.
12. Reuse existing styling classes whenever possible.
13. Preserve existing scheduler behavior unless task explicitly modifies it.
14. Do not create duplicate DB logic.
15. Avoid creating parallel systems when existing systems can be extended.
16. After implementation, perform a self-review:
    - check imports
    - check endpoint consistency
    - check SQL queries
    - check frontend API compatibility
    - check for broken references
    - check for duplicated logic
17. Output ONLY the changed code sections and concise explanation.
18. Minimize token usage.
19. Never refactor entire architecture unless explicitly requested.
20. Maintain current project coding style.
```

---

# BEST IMPLEMENTATION SEQUENCE

This sequence minimizes cascading breakage.

---

# PHASE 1 — ROLE SYSTEM + ADMIN FOUNDATION

## WHY THIS COMES FIRST

Everything else depends on:

- admin permissions
- role separation
- admin dashboard visibility
- assignment approvals
- officer hierarchy

Without stabilizing authority structure first, later phases become messy.

---

# TASK 1A — Create Dedicated Admin Role Flow

## GOAL

Introduce a real admin workflow while preserving existing officer login.

Admins should:

- login from same page
- be redirected differently
- access admin-only panels
- retain global visibility

Normal officers continue unchanged.

---

## REQUIRED CHANGES

### Backend

Modify:

- officers table role handling
- /auth/login response
- visibility guards
- role middleware/helper logic

Add:

- admin role support
- admin dashboard data endpoints

DO NOT:

- change login endpoint path
- change existing response structure
- break officer login

---

### Frontend

Modify login success routing only.

Current flow:

```text
login -> officer dashboard
```

New flow:

```text
if role === admin:
    route -> admin dashboard
else:
    existing dashboard
```

DO NOT:

- redesign login page
- replace dashboard system
- touch unrelated UI

---

## REQUIRED DB CHANGES

Prefer additive migration.

Possible:

```sql
ALTER TABLE officers
MODIFY role ENUM('admin','inspector','viewer');
```

Seed one admin account.

---

## IMPORTANT DESIGN RULE

Admin is NOT a separate authentication system.
Admin is simply another officer role.

This avoids:

- duplicate login logic
- duplicate session logic
- duplicate auth middleware

---

## AI PROMPT FOR TASK 1A

:::writing{variant="standard" id="48371"}
You are modifying an existing Flask + MySQL + single-file frontend CRMS application.

Goal:
Introduce a proper admin role workflow while preserving all existing officer login behavior.

Current system:
- Login endpoint already exists.
- Officers already have role field.
- Frontend currently routes everyone to same dashboard.

Required behavior:
1. Admin logs in from SAME login page.
2. If role=admin -> route to dedicated admin dashboard.
3. All other roles continue existing workflow unchanged.
4. Preserve existing APIs and response formats.
5. Do NOT redesign UI.
6. Do NOT rewrite whole files.
7. Use minimal patching.

Backend tasks:
- Extend role handling safely.
- Add helper guards if needed.
- Add admin-only aggregate endpoints.
- Preserve backward compatibility.

Frontend tasks:
- Add admin routing.
- Add admin dashboard shell using existing styling system.
- Reuse existing components/classes/colors.

Database:
- Use additive migration only.
- Seed one admin account.

Important:
- Do NOT rename endpoints.
- Do NOT modify unrelated UI.
- Do NOT break existing officer dashboard.
- Perform final self-review for API compatibility and broken imports.

Output:
- changed files only
- concise explanations only
- no giant rewrites
:::

---

# TASK 1B — Restrict Case Status Editing + Access Decision Rights

## GOAL

Remove uncontrolled authority from normal officers.

New rules:

- regular officers cannot change case status
- regular officers cannot approve/reject access requests
- ONLY highest-rank officer on a case may approve/reject
- admin may override globally

---

## WHY THIS MUST HAPPEN EARLY

This stabilizes authority hierarchy BEFORE assignment/admin flows become more advanced.

---

## REQUIRED BACKEND CHANGES

Modify:

- PATCH /cases/<id>
- access request approval endpoints
- officer authority helper logic

Create:

```text
get_highest_rank_officer(case_id)
```

Authority logic:

```text
admin -> always allowed
highest ranked assigned officer -> allowed
everyone else -> denied
```

---

## REQUIRED FRONTEND CHANGES

Hide:

- status editing controls
- approve/reject controls

unless:

```text
user is admin
OR
user is highest-ranked officer on that case
```

IMPORTANT:

Hide controls in UI AND enforce in backend.

---

## AI PROMPT FOR TASK 1B

:::writing{variant="standard" id="24811"}
Modify the CRMS authority system.

New rules:
1. Regular officers can no longer change case status.
2. Regular officers can no longer approve/reject access requests.
3. ONLY the highest-ranked officer assigned to a case may approve/reject requests.
4. Admin may always override.

Requirements:
- Preserve all endpoint names.
- Preserve current frontend styling.
- Add backend enforcement, not only frontend hiding.
- Use minimum code modifications.
- Reuse existing helper architecture.
- Do not rewrite entire app.py.

Implementation details:
- Add helper to determine highest-ranked assigned officer.
- Update access decision authorization.
- Update case PATCH authorization.
- Hide unauthorized controls in frontend.

Important:
- Maintain backward compatibility.
- Avoid duplicated authority logic.
- Recheck all permission checks after implementation.

Output only modified code sections.
:::

---

# PHASE 2 — ADMIN CASE CONTROL SYSTEM

---

# TASK 2A — Convert Auto Assignment Into Suggestion Workflow

## GOAL

Current system:

```text
complaint -> algorithm -> direct assignment
```

New system:

```text
complaint -> algorithm suggestion -> admin review -> final assignment
```

THIS IS THE MOST IMPORTANT ARCHITECTURAL CHANGE.

---

## WHY IT COMES AFTER PHASE 1

Because admin role and hierarchy must already exist.

---

## REQUIRED DB CHANGES

Create new table:

```text
assignment_recommendations
```

Suggested structure:

```sql
recommendation_id
case_id
recommended_officer_id
recommended_rank
algorithm_score
recommended_at
approved_by_admin
approved_at
status
```

DO NOT directly assign officers anymore.

---

## REQUIRED ALGORITHM CHANGES

Current:

```text
algorithm creates case_officer rows
```

New:

```text
algorithm only generates recommendations
```

Admin later confirms.

---

## REQUIRED ADMIN DASHBOARD FEATURES

Admin sees:

- pending complaints
- algorithm recommendations
- officer workload
- recommended teams
- ability to add/remove officers
- final approve button

---

## IMPORTANT RULE

DO NOT destroy existing assignment algorithm.

ONLY change:

```text
final output destination
```

from:

```text
case_officer
```

into:

```text
assignment_recommendations
```

---

## AI PROMPT FOR TASK 2A

:::writing{variant="standard" id="77352"}
Refactor the CRMS automated assignment system into an admin-reviewed recommendation workflow.

Current behavior:
- Algorithm directly assigns officers.

New behavior:
- Algorithm generates officer recommendations only.
- Admin reviews recommendations.
- Admin makes final assignment decision.

Requirements:
1. Preserve existing assignment scoring logic.
2. Do NOT rewrite the whole algorithm.
3. Change only the final persistence flow.
4. Add assignment_recommendations table.
5. Add admin endpoints for:
   - viewing recommendations
   - approving assignments
   - modifying officer list before approval
6. Preserve existing UI style.
7. Use additive schema migration.
8. Minimize token usage.

Important:
- Do NOT break scheduler.
- Do NOT remove existing helper methods unless necessary.
- Keep backward compatibility where possible.
- Existing algorithm should still compute the same recommendations.

Final review required:
- check DB transactions
- check duplicate assignment prevention
- check recommendation approval flow
:::

---

# TASK 2B — Mid-Case Officer Management

## GOAL

Admin must:

- add officers mid-case
- remove officers mid-case
- rebalance investigations dynamically

---

## REQUIRED CHANGES

### Backend

Add:

```text
POST /cases/<id>/officers/add
DELETE /cases/<id>/officers/remove
```

Log changes.

DO NOT reuse dangerous generic assignment endpoint directly.

---

### Frontend

Inside admin case view:

- officer search
- add/remove controls
- current assignment visibility

---

## IMPORTANT RULE

Every reassignment must:

- update workload metrics
- trigger assignment email
- preserve historical logs

---

## AI PROMPT FOR TASK 2B

:::writing{variant="standard" id="51026"}
Extend the CRMS assignment system to support dynamic officer reassignment during active cases.

Requirements:
1. Admin can add officers to existing cases.
2. Admin can remove officers from existing cases.
3. Preserve existing assignment structures.
4. Add dedicated endpoints instead of overloading old ones.
5. Trigger email notifications when assignments change.
6. Preserve current UI design language.
7. Use minimal code edits.

Important:
- Do not break workload calculations.
- Maintain assignment history integrity.
- Avoid duplicate officer assignments.
- Preserve backward compatibility.

Perform final review for:
- duplicate assignments
- orphaned references
- authorization enforcement
- broken frontend fetch calls
:::

---

# PHASE 3 — COMMUNICATION + DOCUMENT SYSTEM

---

# TASK 3A — Officer Assignment Email System

## GOAL

When officer assigned:

- send assignment email
- include teammate list
- include generated case PDF

Also support:

- resend dossier during investigation

---

## WHY THIS IS SEPARATE

Email systems are failure-prone.

Keeping them isolated prevents breaking case logic.

---

## REQUIRED BACKEND CHANGES

Extend existing:

- email_utils.py

DO NOT rewrite PDF generation.
Existing PDF system is already good.

Add:

```text
send_case_assignment_email()
send_case_update_email()
```

---

## REQUIRED NEW ENDPOINT

```text
POST /cases/<id>/email-dossier
```

Officer can request latest case PDF.

---

## IMPORTANT RULE

Email failures must NEVER fail assignment transaction.

Use async thread model already existing.

---

## AI PROMPT FOR TASK 3A

:::writing{variant="standard" id="81449"}
Extend the CRMS email system.

Required features:
1. Send email when officer gets assigned to a case.
2. Include:
   - case PDF
   - teammate list
   - case details
3. Allow officers to request updated dossier emails during active investigations.
4. Reuse existing PDF generation system.
5. Reuse existing async email threading model.

Important:
- Do NOT rewrite email_utils.py entirely.
- Additive changes only.
- Preserve current SMTP fallback behavior.
- Email failures must not break assignment operations.
- Preserve existing endpoint compatibility.

Frontend:
- Add lightweight trigger button only.
- Reuse existing styles.

Perform final review for:
- async execution
- PDF generation integrity
- duplicate mail sending
- import consistency
:::

---

# PHASE 4 — CASE TIMELINE + EVIDENCE SYSTEM

---

# TASK 4A — Timeline Notes + Evidence Uploads

## GOAL

Allow officers to:

- append timeline updates
- upload evidence
- upload PDFs
- upload audio
- upload videos
- upload images

WITHOUT bloating cases table.

---

# BEST DATABASE DESIGN

DO NOT store files in MySQL blobs.

Use:

```text
filesystem/cloud storage + DB metadata
```

Best structure:

```text
/uploads/cases/<case_id>/
```

DB only stores:

```text
file path
mime type
uploaded_by
uploaded_at
caption
```

---

## REQUIRED TABLES

### case_updates

```sql
update_id
case_id
officer_id
update_text
created_at
```

### case_evidence

```sql
evidence_id
case_id
uploaded_by
file_name
file_path
mime_type
file_size
uploaded_at
notes
```

---

## IMPORTANT RULE

DO NOT overload existing cases.description.

That field should remain initial incident narrative.

Timeline becomes separate append-only system.

---

## FRONTEND DESIGN

Inside case details:

```text
Timeline Tab
Evidence Tab
```

Reuse existing modal structure.

---

## AI PROMPT FOR TASK 4A

:::writing{variant="standard" id="62108"}
Extend the CRMS case system with timeline updates and evidence uploads.

Required features:
1. Officers can append investigation updates over time.
2. Officers can upload:
   - images
   - videos
   - audio
   - PDFs
   - general documents
3. Preserve existing case description as original complaint narrative.
4. Build append-only timeline architecture.
5. Store files on filesystem, not MySQL blobs.
6. Store only metadata in DB.
7. Reuse existing UI style and modal system.

Required tables:
- case_updates
- case_evidence

Important:
- Do NOT redesign frontend.
- Do NOT rewrite case detail system.
- Additive architecture only.
- Validate upload size/type safely.
- Keep upload paths organized by case_id.

Perform final review for:
- upload security
- path traversal safety
- MIME validation
- orphaned files
- API compatibility
:::

---

# PHASE 5 — DATABASE NORMALIZATION

---

# TASK 5A — Merge public_complaints Into Unified Intake System

## GOAL

Eliminate duplicate complaint storage.

Current problem:

```text
public_complaints -> copied into cases
```

This duplicates:

- complainant data
- incident description
- crime type
- location

---

# BEST SOLUTION

YES.
Use ONE unified cases table.

Add intake statuses.

---

## RECOMMENDED STATUS FLOW

Expand case lifecycle:

```text
Pending Review
Recommended
Assigned
Active
Solved
Closed
Rejected
```

---

## IMPORTANT DESIGN SHIFT

Public complaints become:

```text
cases.source = 'public'
status = 'Pending Review'
```

NOT a separate table.

---

## WHY THIS COMES LAST

Because this is destructive architecture work.

Earlier phases depend on existing complaint flow.

Changing this too early would break:

- scheduler
- recommendation engine
- dashboards
- complaint promotion
- analytics

---

## REQUIRED MIGRATION STRATEGY

DO NOT directly delete public_complaints.

Safe migration:

### Step 1

Add new statuses.

### Step 2

Update backend logic to support unified flow.

### Step 3

Migrate old complaint data.

### Step 4

Switch scheduler.

### Step 5

Only then deprecate public_complaints.

---

## AI PROMPT FOR TASK 5A

:::writing{variant="standard" id="39714"}
Refactor the CRMS complaint intake architecture into a unified cases table workflow.

Current problem:
- public_complaints duplicates data already stored later in cases.

New architecture:
- Public complaints should directly create rows in cases.
- Lifecycle controlled through status field.
- Use statuses like:
  - Pending Review
  - Recommended
  - Assigned
  - Active
  - Solved
  - Closed
  - Rejected

Requirements:
1. Preserve backward compatibility during migration.
2. Use staged migration approach.
3. Do NOT immediately remove public_complaints.
4. Update scheduler and recommendation logic gradually.
5. Minimize code rewrites.
6. Preserve existing API contracts where possible.

Important:
- This is a high-risk migration.
- Avoid breaking analytics.
- Avoid breaking assignment flow.
- Avoid destructive SQL early.

Perform final review for:
- migration integrity
- duplicate data prevention
- scheduler compatibility
- analytics compatibility
:::

---

# FINAL RECOMMENDED EXECUTION ORDER

```text
1A  Admin Role System
1B  Authority Restrictions
2A  Recommendation-Based Assignment System
2B  Dynamic Officer Assignment Management
3A  Officer Email + PDF Dispatch System
4A  Timeline + Evidence Upload System
5A  Unified Complaint Intake Refactor
```

---

# ADDITIONAL CRITICAL ENGINEERING ADVICE

## DO NOT LET AI:

- reformat entire files
- rewrite app.py completely
- replace SQL architecture wholesale
- migrate frontend framework
- split frontend into React suddenly
- introduce JWT overhaul mid-project
- add massive ORM migration
- replace existing fetch structure

---

# BEST AI WORKFLOW

For every phase:

```text
1. Create migration first
2. Patch backend
3. Test endpoints
4. Patch frontend
5. Run compatibility review
6. Only then move to next phase
```

---

# BEST PRACTICE FOR CLAUDE CODE / ANTIGRAVITY

At the start of EVERY task:

```text
First analyze the existing architecture and identify ONLY the exact files and functions that need modification.
Do not rewrite entire files.
Do not redesign UI.
Preserve API compatibility.
Minimize token usage.
```

---

# FINAL STRATEGIC NOTE

Your project is already beyond beginner level.

The current backend structure is actually solid:

- helper separation exists
- scheduler exists
- role structure exists
- PDF engine exists
- email async exists
- assignment engine exists
- DB separation exists

So the correct strategy is NOT rebuilding.

The correct strategy is:

```text
controlled evolution
```

That is how large real systems survive.

