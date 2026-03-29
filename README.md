# Cycle-Safe Referral Engine

Graph-based referral SaaS with cycle prevention, multi-level rewards, fraud detection, admin auth, and a React operations dashboard.

## Screenshots

### Dashboard Overview
![Dashboard Overview](docs/screenshots/dashboard-overview.png)

### User Profile Panel
![User Profile Panel](docs/screenshots/user-profile.png)

This repo currently contains:
- FastAPI backend
- PostgreSQL persistence with Alembic migrations
- in-memory DAG cache for fast cycle checks
- JWT auth + refresh-session flow for admins
- organisation-scoped admin APIs
- React admin dashboard
- Postman collection and a full manual test guide

## What It Does
The engine models referrals as a directed graph.

Core guarantees:
- a child can only have one active parent
- self-referrals are blocked
- duplicate claims are blocked
- cycle-forming claims are blocked before commit
- rewards propagate upward by configurable depth
- fraud events are logged and exposed to admins

The current implementation is designed as a scalable modular monolith:
- PostgreSQL is the source of truth
- the DAG is cached in memory for fast traversal
- APIs are organisation-scoped using `org_id` from JWT claims
- reward config is versioned
- admin activity is audited

## Current Feature Set

### Backend
- `POST /referral/claim`
- `GET /dashboard/metrics`
- `GET /dashboard/activity`
- `GET /reward/config`
- `PUT /reward/config`
- `POST /simulate`
- `GET /user/search`
- `GET /user`
- `GET /user/{id}/profile`
- `GET /user/{id}/graph`
- `GET /user/{id}/rewards`
- `PUT /user/{id}/status`
- `GET /fraud/flags`
- `POST /fraud/{id}/flag`
- `POST /fraud/{id}/unflag`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /auth/sessions`
- `POST /auth/sessions/revoke-others`
- `DELETE /auth/sessions/{id}`
- `GET /admin/orgs`
- `POST /admin/orgs`
- `PUT /admin/orgs/{id}/suspend`
- `GET /admin/audit-log`
- `GET /admin/team`
- `POST /admin/team/invite`
- `PUT /admin/team/{id}/role`
- `DELETE /admin/team/{id}`
- `POST /admin/seed-config`

### Frontend
- login page
- metrics panel
- DAG explorer
- fraud monitor
- activity feed via websocket
- user profile panel
- audit log panel
- session management panel

### Tooling
- Alembic migrations
- seed script with demo data
- Postman collection
- detailed Postman E2E test guide

## Architecture Summary
- Backend: FastAPI + SQLAlchemy async
- Database: PostgreSQL
- Auth: JWT access token + refresh cookie sessions
- Graph engine: in-memory DAG cache with mutation lock
- Frontend: React + Vite
- Graph rendering: React Flow

Write path summary:
1. validate referral request
2. check fraud conditions
3. run cycle detection against DAG cache
4. commit referral to PostgreSQL
5. create reward transactions
6. publish activity event
7. update in-memory graph

## Repo Structure

```text
D:\Projects\Learning
+-- backend/
¦   +-- alembic/
¦   +-- app/
¦   ¦   +-- routes/
¦   ¦   +-- services/
¦   ¦   +-- auth.py
¦   ¦   +-- config.py
¦   ¦   +-- dag_engine.py
¦   ¦   +-- database.py
¦   ¦   +-- models.py
¦   ¦   +-- schemas.py
¦   +-- requirements.txt
¦   +-- seed.py
+-- docs/
¦   +-- screenshots/
+-- frontend/
¦   +-- src/
¦   ¦   +-- components/
¦   ¦   +-- api.js
¦   ¦   +-- App.jsx
¦   +-- package.json
+-- postman/
¦   +-- Cycle-Safe-Referral-Engine.postman_collection.json
¦   +-- Cycle-Safe-Referral-Engine.local.postman_environment.json
+-- ADMIN_PLAN.md
+-- POSTMAN_TEST_FLOW.md
+-- README.md
```

## Prerequisites
- Python 3.12
- PostgreSQL 18.x locally installed
- Node.js 18+

## Local Setup

### 1. Database
Create the database if needed:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\createdb.exe' -U postgres referral_db
```

Default connection used by this repo:

```env
DATABASE_URL=postgresql+asyncpg://postgres:1234@localhost:5432/referral_db
```

### 2. Backend

```powershell
cd D:\Projects\Learning\backend
python -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic -c .\alembic.ini upgrade head
python seed.py
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend URLs:
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### 3. Frontend

```powershell
cd D:\Projects\Learning\frontend
npm install
npm run dev
```

Frontend URL:
- `http://localhost:5173`

## Seeded Admin Credentials

### Org admin
- email: `admin@example.com`
- password: `admin123`

### Super admin
- email: `owner@example.com`
- password: `Owner123!`

## Postman Assets
Import these into Postman:
- [postman/Cycle-Safe-Referral-Engine.postman_collection.json](D:/Projects/Learning/postman/Cycle-Safe-Referral-Engine.postman_collection.json)
- [postman/Cycle-Safe-Referral-Engine.local.postman_environment.json](D:/Projects/Learning/postman/Cycle-Safe-Referral-Engine.local.postman_environment.json)

For the full manual API walkthrough, use:
- [POSTMAN_TEST_FLOW.md](D:/Projects/Learning/POSTMAN_TEST_FLOW.md)

## Testing Notes
The best complete end-to-end API flow right now is:
1. login as seeded org admin
2. inspect users
3. run claim happy path
4. verify metrics, rewards, graph, and activity
5. run edge cases: self-referral, duplicate, already-referred, cycle, velocity
6. verify fraud and audit outputs

Important current limitation:
- creating a new organisation is implemented
- fully bootstrapping the first org admin for that newly created organisation is not yet completed purely through APIs

## Known Functional Areas
Implemented and testable:
- cycle-safe claims
- velocity fraud checks
- reward propagation
- org-scoped admin auth
- audit log read path
- session revocation
- user profile inspection
- fraud manual flag and unflag

Still incomplete or partially implemented:
- full first-admin onboarding for a newly created org
- fraud review queue workflow
- campaign manager
- payout approval queue
- advanced webhooks/notifications
- full team-management UI polish
