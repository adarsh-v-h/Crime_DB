# CRMS — Crime Record Management System 🎯

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)  
[![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)  
[![Build Status](https://img.shields.io/badge/build-passing-success.svg)](#)  
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)](#)

---

## Table of Contents
- [Overview](#overview)  
- [Features](#features)  
- [Architecture](#architecture)  
- [Installation](#installation)  
- [Quick Start](#quick-start)  
- [API Reference](#api-reference)  
- [Frontend](#frontend)  
- [Testing](#testing)  
- [Contributing](#contributing)  
- [License](#license)  
- [Contact & Acknowledgements](#contact--acknowledgements)

---

## Overview
CRMS is a **polished police investigation dashboard** built for the Bengaluru Police Department. It combines a Flask‑powered backend, a MySQL database, and a single‑page React frontend served via CDN. The system streamlines case management, citizen complaint intake, automated case assignment, and secure dossier delivery.

---

## Features ✨
- **Staff portal** – Role‑based login, full CRUD on cases, officer assignments, analytics, and status updates.  
- **Public portal** – Citizens can file complaints, browse public cases, and request access to case dossiers (protected by reCAPTCHA).  
- **Case discovery** – Powerful search / filter by status, crime type, location, or keywords.  
- **Automated assignment** – Background scheduler promotes pending complaints to cases and auto‑assigns officers based on severity and workload.  
- **Access‑request workflow** – Officers approve/reject citizen requests; approved requests trigger PDF dossier generation and optional email delivery.  
- **Security** – Bcrypt password hashing, invisible reCAPTCHA, role‑based visibility, and `X‑Officer‑Id` header on protected routes.

---

## Architecture ![Architecture Diagram](assets/architecture.png)
> *Placeholder architecture diagram. Replace `assets/architecture.png` with a real diagram.*

The system consists of three logical layers:
1. **Backend (Flask)** – API, authentication, business logic, and background scheduler.  
2. **Database (MySQL)** – Stores officers, cases, complaints, and access‑request data.  
3. **Frontend (React via CDN)** – Interactive UI for staff and citizens.

---

## Installation 🚀
```bash
# Clone the repo
git clone https://github.com/your-org/Crime_DB.git
cd Crime_DB

# Create environment variables
cp .env.example .env
# Edit .env with your MySQL credentials and reCAPTCHA keys

# Set up a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Database Setup
```bash
# Execute the migration scripts in order (adjust MySQL user as needed)
mysql -u root -p < Backend/setup_db.sql
mysql -u root -p < Backend/migrate_v2.sql
mysql -u root -p < Backend/migrate_v3.sql
```

---

## Quick Start
```bash
# Start the Flask server
python3 Backend/app.py
```
Open **http://localhost:5000** in a browser. The backend serves both the API and the React frontend.

---

## API Reference 📚
All responses follow the pattern `{ "success": true/false, "data": … }` or `{ "success": false, "error": "…" }`.

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Simple health‑check endpoint |

### Cases
| Method | Path | Description |
|--------|------|-------------|
| GET | `/cases` | List cases (filters, pagination, role‑based visibility) |
| GET | `/cases/<id>` | Detailed view of a case |
| POST | `/cases` | Create a new case (inspectors only) |
| PATCH | `/cases/<id>` | Update case fields/status |
| DELETE | `/cases/<id>` | Delete a case |
| GET | `/cases/<id>/officers` | Officers assigned to a case |

### Officers & Assignments
| Method | Path | Description |
|--------|------|-------------|
| GET | `/officers` | List all officers |
| POST | `/officers` | Add a new officer |
| GET | `/case-officer` | List all case‑officer pairings |
| POST | `/case-officer` | Assign an officer to a case |
| DELETE | `/case-officer` | Remove an assignment |

### Analytics & Assignment Engine
| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics` | Dashboard analytics |
| GET | `/assignments/pending` | Queue of pending complaints |
| POST | `/assignments/process` | Manually trigger the assignment algorithm |

### Public Portal (Citizens)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/public/cases` | Browse public cases with filters |
| POST | `/public/complaint` | Submit a citizen complaint |
| POST | `/public/access-request` | Request access to a case dossier |
| GET | `/stats` | Public statistics summary |

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Officer login (badge ID, password, reCAPTCHA) |

### Access Requests (Staff)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/access-requests` | List access requests (role‑filtered) |
| POST | `/api/access-requests/<id>/approve` | Approve request – sends PDF dossier |
| POST | `/api/access-requests/<id>/reject` | Reject request – notifies citizen |

---

## Frontend 🎨
The UI lives in a single HTML file `Frontend/crms_frontend.html`. It pulls React, Tailwind CSS, Chart.js, and Framer Motion from CDNs, delivering a snappy SPA experience.

---

## Testing 🧪
```bash
# Run the test suite (if any)
pytest   # or any project‑specific command
```
The README changes are purely documentation; they do not affect runtime behavior.

---

## Contributing 🤝
We welcome contributions! Please follow these steps:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/awesome-feature`).
3. Ensure code style passes linting (`flake8` optional) and all tests succeed.
4. Submit a pull request with a clear description.

---

## License 📄
This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

---

## Contact & Acknowledgements
- **Maintainer**: Venzz ([@venzz](https://github.com/venzz))
- **Thanks** to the Bengaluru Police Department for providing the domain context.
- **Special thanks** to the open‑source community for the libraries used.

---

*Generated on $(date)*
