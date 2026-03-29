# Referral Engine — Claude Code Project Memory

This file is automatically read by Claude Code at the start of every session.
It gives Claude the full project context so you never have to re-explain the architecture.

---

## 🎯 What This Project Is

A **cycle-safe referral engine** — a backend API + React dashboard that manages user referral
relationships as a Directed Acyclic Graph (DAG). The core guarantee: no referral chain can
ever form a loop. Cycle detection runs in-memory using BFS in under 100ms.

Think of it like the fraud-protection backend behind Swiggy or PhonePe's "refer a friend" system.

---

## 🏗️ Architecture Summary

- **Backend:** Python 3.11 + FastAPI (async) — lives in `backend/`
- **Database:** PostgreSQL 15 — ORM via SQLAlchemy async, migrations via Alembic
- **Graph engine:** `backend/app/dag_engine.py` — in-memory adjacency dict, BFS cycle check
- **Fraud layer:** `backend/app/fraud.py` — velocity, self-referral, duplicate, cycle
- **Reward engine:** `backend/app/rewards.py` — multi-level propagation, configurable depth
- **Frontend:** React 18 + Vite + react-flow — lives in `frontend/`
- **Entry point:** `docker-compose.yml` — runs everything with one command

---

## 🧠 The Most Important File

`backend/app/dag_engine.py` is the heart of the project.

It holds:
- An in-memory adjacency dict `{user_id: set(parent_ids)}`
- `add_edge(child, parent)` — commits a referral edge
- `has_path(source, target)` — BFS, returns True if a directed path exists
- `get_ancestors(user_id, depth)` — walks up N levels for reward propagation
- `rebuild_from_db()` — called on startup to sync from Postgres

**Never bypass this class to write directly to the `referrals` table.** All edge operations must go through `dag_engine` so the in-memory graph stays consistent with the DB.

---

## 📐 Coding Conventions

- **Python:** Use `async`/`await` everywhere. No sync DB calls in route handlers.
- **Type hints:** Required on all function signatures.
- **Pydantic schemas:** All request/response bodies must have a schema in `schemas.py`.
- **UUIDs:** All primary keys are UUIDs. Never use auto-increment integers.
- **No direct SQL:** Use SQLAlchemy ORM. Raw SQL only in `seed.py` if needed.
- **Error responses:** Always return structured JSON `{"detail": "..."}` — never plain strings.
- **React:** Functional components only. No class components. Use hooks.
- **API calls:** All frontend API calls go through `src/api.js` — never fetch directly in components.

---

## 🚫 Hard Rules — Never Break These

1. **Never commit an edge that would create a cycle.** Always run `dag_engine.has_path(parent, child)` before `dag_engine.add_edge(child, parent)`. These two checks must be inside the same async mutex.

2. **Never skip the fraud pre-checks.** The order is: self-referral check → duplicate check → velocity check → BFS cycle check → commit. All four must run on every `/referral/claim` call.

3. **Never propagate rewards to a flagged user.** In `rewards.py`, stop the ancestor walk when `user.status == 'flagged'`. Do not skip and continue upward.

4. **Never hardcode reward values.** Always read from the `reward_config` table, snapshotted at the start of each claim transaction.

5. **Never let two coroutines write to the in-memory DAG simultaneously.** The `asyncio.Lock` in `dag_engine.py` must wrap both the `has_path` check and the `add_edge` call as one atomic block.

---

## 🔌 API Endpoint Map

| Method | Path | File |
|---|---|---|
| POST | `/referral/claim` | `routes/referrals.py` |
| GET | `/user/{id}/graph` | `routes/users.py` |
| GET | `/user/{id}/rewards` | `routes/users.py` |
| GET | `/fraud/flags` | `routes/fraud.py` |
| GET | `/dashboard/metrics` | `routes/dashboard.py` |
| GET/PUT | `/reward/config` | `routes/dashboard.py` |
| POST | `/simulate` | `routes/dashboard.py` |
| POST | `/seed` | `routes/dashboard.py` (dev only) |

---

## 🗄️ Database Tables

- `users` — nodes of the graph
- `referrals` — directed edges (child → parent), unique on `(child_id, parent_id)`
- `fraud_flags` — every rejected claim with reason
- `reward_transactions` — append-only ledger, never update rows
- `reward_config` — single active row with current reward rules

---

## 🌱 Environment Variables

All in `backend/.env`:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/referral_db
MAX_CLAIMS_PER_MINUTE=5
REWARD_MAX_DEPTH=3
DEBUG=true
```

---

## 🚀 How to Run

```bash
# Full stack (Docker)
docker-compose up --build

# Seed data
docker-compose exec backend python seed.py

# Backend only (local dev)
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend only (local dev)
cd frontend && npm run dev
```

Swagger UI: `http://localhost:8000/docs`
Dashboard: `http://localhost:5173`

---

## ✅ What "Done" Looks Like for Each Feature

- **Referral claim:** Returns `{status: "accepted", rewards: [...]}` or `{status: "rejected", reason: "..."}` in < 100ms
- **Graph endpoint:** Returns nested JSON tree, max 3 levels, includes user status on each node
- **Dashboard metrics:** Returns counts for users, referrals, valid, rejected, fraud, total rewards
- **Fraud flags:** Returns paginated list sorted by timestamp descending
- **Seed script:** Creates 50 users, at least 3 cycle attempts (blocked), at least 2 velocity violations

---

## 📝 Current Status

> Update this section as you build. Claude reads it at session start.

- [ ] DB models + migrations
- [ ] DAG engine class
- [ ] FastAPI skeleton + all route stubs
- [ ] `/referral/claim` with full fraud + cycle logic
- [ ] Reward propagation
- [ ] Remaining read endpoints
- [ ] React dashboard — 4 panels
- [ ] Seed script
- [ ] Docker setup
- [ ] ARCHITECTURE.md
