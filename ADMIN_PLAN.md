# 🔐 Admin Dashboard — Full Feature Plan & Fix Log

> Generated from admin perspective review of the Cycle-Safe Referral Engine dashboard.
> Covers: auth architecture, multi-tenancy, all admin features, current fixes, and phased build order.

---

## 📸 Current Build Status (from screenshot review)

### What's working
- Metrics panel — all 6 stats present (Total Users, Total Referrals, Rewards Distributed, Accepted Claims, Rejected Claims, Fraud Alerts)
- Fraud monitor — USER ID, TIMESTAMP, REASON columns with correct colour-coded badges (Cycle Blocked = red, Velocity Limit = amber)
- Activity feed — WebSocket connected, CONNECTED indicator showing (bonus feature, done)
- Dark theme and overall layout — clean and production-quality

### Fixes required before new features

| # | Issue | Root Cause | Fix |
|---|---|---|---|
| 1 | **DAG Explorer graph canvas is empty** | react-flow not rendering on lookup, OR `GET /user/{id}/graph` returning bad data | Hit `curl http://localhost:8000/user/<uuid>/graph` directly. If data returns → fix GraphView.jsx prop mapping to react-flow. If error → fix the route handler. |
| 2 | **Rewards Distributed shows ₹0.00** | `reward_config` table has no active row, so reward engine silently skips propagation | Run: `SELECT * FROM reward_config LIMIT 1;` and `SELECT COUNT(*) FROM reward_transactions;` — if empty, seed: `INSERT INTO reward_config (id, max_depth, reward_type, reward_value) VALUES (gen_random_uuid(), 3, 'fixed', '[10, 5, 2]');` then re-trigger claims |
| 3 | **User ID truncated in fraud monitor with no way to copy** | Display only shows first 8 chars, no tooltip or copy button | Add tooltip showing full UUID on hover + copy-to-clipboard icon. Without this, admin cannot use those IDs to look up users in DAG Explorer |
| 4 | **Activity feed content unverified** | Feed is cut off in screenshot — "Seed Completed" partially visible | Scroll down and verify event messages are human-readable strings ("User A referred User B", "Cycle prevented: C → A", "Reward: ₹10 to X") — not raw JSON blobs |

---

## 🏗️ The Core Problem — Multi-Tenancy Must Come First

The dashboard currently has **no concept of who is looking at it** and **no separation between organisations**. This is fine for a solo dev demo. The moment a second organisation uses this engine:

> **Swiggy's referral data cannot be visible to Zomato's admin. Ever.**

The auth question and the multi-tenancy question are the **same question** and must be answered together before any new feature is built. Adding `org_id` retroactively — after fraud management, campaigns, and analytics are built — means touching every table, every query, and every route. Do it now.

---

## 👥 Identity Model — Three Tiers

```
                        ┌─────────────────────┐
                        │     Super Admin      │
                        │   (engine owner)     │
                        │  Sees all orgs,      │
                        │  all data, billing   │
                        └──────────┬──────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
   ┌──────▼──────┐          ┌──────▼──────┐         ┌──────▼──────┐
   │  Org Admin  │          │  Org Admin  │         │  Org Admin  │
   │  (Swiggy)   │          │  (Zomato)   │         │   (CRED)    │
   │ Sees only   │          │ Sees only   │         │ Sees only   │
   │ Swiggy data │          │ Zomato data │         │ CRED data   │
   └──────┬──────┘          └─────────────┘         └─────────────┘
          │
   ┌──────┴──────────────┐
   │                     │
┌──▼──────┐        ┌─────▼────┐
│ Manager │        │ Analyst  │
│ Read +  │        │ Read     │
│ Approve │        │ only     │
└─────────┘        └──────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Data isolation boundary — orgs cannot see each other
Every DB query filters by org_id from the JWT token
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Role permissions matrix

| Action | Super Admin | Org Admin | Manager | Analyst |
|---|---|---|---|---|
| View all orgs | ✅ | ❌ | ❌ | ❌ |
| Create / delete org | ✅ | ❌ | ❌ | ❌ |
| View own org data | ✅ | ✅ | ✅ | ✅ |
| Edit reward config | ✅ | ✅ | ❌ | ❌ |
| Manual flag / unflag user | ✅ | ✅ | ✅ | ❌ |
| Approve fraud queue items | ✅ | ✅ | ✅ | ❌ |
| Manual reward adjustment | ✅ | ✅ | ❌ | ❌ |
| View audit log | ✅ | ✅ | ✅ | ✅ |
| Export data | ✅ | ✅ | ✅ | ❌ |
| Manage team members | ✅ | ✅ | ❌ | ❌ |
| View billing | ✅ | ✅ | ❌ | ❌ |
| Configure webhooks | ✅ | ✅ | ❌ | ❌ |
| Manage API keys | ✅ | ✅ | ❌ | ❌ |

---

## 🔑 Auth Architecture

### How login works

```
User enters email + password (or clicks Google SSO)
              │
              ▼
       Auth Service (FastAPI)
       Verify credentials
       Issue JWT token
              │
     ┌────────┴────────┐
     │                 │
role = super_admin   role = org_admin / manager / analyst
     │                 │
     ▼                 ▼
Super admin view    Org-scoped view
No org filter       org_id injected on every DB call
All orgs visible    Cannot see other orgs
```

### What the JWT carries

```json
{
  "user_id": "uuid",
  "org_id": "uuid",
  "role": "org_admin",
  "email": "admin@swiggy.com",
  "expires_at": "2026-04-05T00:00:00Z"
}
```

**The `org_id` comes from the verified token only — never from a query parameter the client sends.** A client sending `?org_id=other-org-uuid` must be ignored. The token is the only source of truth.

### FastAPI implementation pattern

```python
# One dependency, injected into every route
async def get_current_org(token: str = Depends(oauth2_scheme)) -> str:
    payload = verify_jwt(token)
    return payload["org_id"]

# Every query uses it — org A structurally cannot read org B's data
async def get_fraud_flags(org_id: str = Depends(get_current_org)):
    return db.query(FraudFlag).filter(FraudFlag.org_id == org_id).all()
```

### New database columns required (migration)

Add `org_id UUID NOT NULL REFERENCES organisations(id)` to:
- `users`
- `referrals`
- `fraud_flags`
- `reward_transactions`
- `reward_config`

Add index on `org_id` for each table. All existing rows get assigned to a default `org_id` during migration.

---

## 🗄️ New Tables Required

### `organisations`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | VARCHAR | e.g. "Swiggy" |
| `domain` | VARCHAR | e.g. "swiggy.com" — used for SSO routing |
| `plan` | ENUM | `free` / `pro` / `enterprise` |
| `status` | ENUM | `active` / `suspended` / `churned` |
| `max_users` | INT | Plan limit, NULL = unlimited |
| `max_depth` | INT | Per-org referral depth override |
| `api_rate_limit` | INT | Claims per minute allowed |
| `created_at` | TIMESTAMPTZ | |

### `admin_users`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK → organisations | NULL for super admins |
| `email` | VARCHAR UNIQUE | |
| `password_hash` | VARCHAR | bcrypt, NULL if SSO-only |
| `role` | ENUM | `super_admin` / `org_admin` / `manager` / `analyst` |
| `totp_secret` | VARCHAR | Nullable — only if 2FA enabled |
| `totp_enabled` | BOOLEAN | Default false |
| `status` | ENUM | `active` / `suspended` / `invited` |
| `last_login_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ | |

### `admin_sessions`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `admin_user_id` | UUID FK | |
| `refresh_token_hash` | VARCHAR | Hashed refresh token |
| `device_hint` | VARCHAR | "Chrome on macOS" |
| `ip_address` | INET | |
| `last_active_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ | |
| `revoked` | BOOLEAN | Default false |

### `api_keys`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | |
| `key_hash` | VARCHAR | Never store plaintext |
| `name` | VARCHAR | "Production key", "Staging key" |
| `last_used_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ | Nullable |
| `revoked` | BOOLEAN | Default false |
| `created_by` | UUID FK → admin_users | |
| `created_at` | TIMESTAMPTZ | |

### `audit_log`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | |
| `actor_id` | UUID FK → admin_users | Who did it |
| `action` | VARCHAR | e.g. `user.flag`, `reward.adjust`, `config.update` |
| `resource_type` | VARCHAR | `user` / `referral` / `fraud_flag` / `reward_config` |
| `resource_id` | UUID | Which record was affected |
| `before_state` | JSONB | Snapshot before change |
| `after_state` | JSONB | Snapshot after change |
| `ip_address` | INET | |
| `timestamp` | TIMESTAMPTZ | Immutable once written |

### `campaigns`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | |
| `name` | VARCHAR | "Diwali 2x Bonus" |
| `reward_multiplier` | NUMERIC | e.g. 2.0 for 2× |
| `override_config` | JSONB | Full reward config override, nullable |
| `target_segment` | JSONB | User filter rules, nullable = all users |
| `starts_at` | TIMESTAMPTZ | |
| `ends_at` | TIMESTAMPTZ | |
| `status` | ENUM | `draft` / `active` / `ended` / `cancelled` |
| `created_by` | UUID FK → admin_users | |
| `created_at` | TIMESTAMPTZ | |

### `fraud_review_queue`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | |
| `referral_id` | UUID FK → referrals | The claim under review |
| `risk_score` | NUMERIC | 0.0–1.0, from scoring engine |
| `reason` | VARCHAR | Why it was flagged for review |
| `status` | ENUM | `pending` / `approved` / `rejected` |
| `reviewed_by` | UUID FK → admin_users | Nullable |
| `review_note` | TEXT | Nullable |
| `reviewed_at` | TIMESTAMPTZ | Nullable |
| `created_at` | TIMESTAMPTZ | |

### `webhooks`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | |
| `url` | VARCHAR | Target endpoint |
| `events` | TEXT[] | `["referral.claimed", "fraud.flagged", "reward.paid"]` |
| `secret` | VARCHAR | HMAC signing secret, hashed |
| `active` | BOOLEAN | Default true |
| `last_fired_at` | TIMESTAMPTZ | |
| `failure_count` | INT | Consecutive failures |
| `created_at` | TIMESTAMPTZ | |

### `webhook_deliveries`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `webhook_id` | UUID FK | |
| `event_type` | VARCHAR | |
| `payload` | JSONB | What was sent |
| `response_status` | INT | HTTP status received |
| `response_body` | TEXT | Nullable |
| `attempt_count` | INT | Retry count |
| `delivered_at` | TIMESTAMPTZ | Nullable — NULL = failed |
| `created_at` | TIMESTAMPTZ | |

### `notifications`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | |
| `admin_user_id` | UUID FK | Target recipient, nullable = all org admins |
| `type` | ENUM | `fraud_spike` / `reward_config_change` / `payout_approval_needed` / `system_health` |
| `title` | VARCHAR | |
| `body` | TEXT | |
| `read` | BOOLEAN | Default false |
| `created_at` | TIMESTAMPTZ | |

---

## 📋 Full Feature List by Category

---

### 1. Auth & Identity

#### 1.1 Email + password login — CRITICAL
- Login form: email + password
- Password hashed with bcrypt (never stored plaintext)
- On success: issue short-lived JWT access token (15 min) + long-lived refresh token (7 days)
- Refresh token rotated on each use (sliding window)
- Lock account after 5 consecutive failed attempts — unlock via email link or super admin

#### 1.2 Google OAuth / SSO — CRITICAL
- "Sign in with Google" button on login page
- Enterprise orgs configure their own Google Workspace domain
- User's `org_id` resolved from their email domain against the `organisations` table
- SAML 2.0 support for Okta, Azure AD, Salesforce SSO (phase 4)

#### 1.3 Role-based access control (RBAC) — CRITICAL
- Four roles: `super_admin`, `org_admin`, `manager`, `analyst`
- Role embedded in JWT — checked server-side on every route
- Frontend hides UI elements the role cannot access
- Backend enforces regardless of what the frontend shows

#### 1.4 Two-factor authentication (2FA) — IMPORTANT
- TOTP via Google Authenticator or Authy
- Setup flow: show QR code → user scans → confirm with 6-digit code → enable
- Mandatory for `super_admin`, optional (but prompted) for `org_admin`
- Backup codes generated at setup (one-time use, hashed in DB)
- Recovery: email link to disable 2FA if device is lost

#### 1.5 Session management — IMPORTANT
- Admin can see all active sessions: device, IP, location (reverse geo), last active timestamp
- "Revoke this session" button on each row
- "Revoke all other sessions" for security incidents
- Sessions auto-expire after 30 days inactivity

#### 1.6 Password policy + reset — IMPORTANT
- Forgot password: send time-limited link (15 min expiry) to registered email
- Minimum password requirements: 10 chars, one uppercase, one number, one special char
- Enforce via zxcvbn strength meter on frontend
- Cannot reuse last 5 passwords (hashed history kept)

---

### 2. Organisation & Tenant Management

#### 2.1 Org onboarding — CRITICAL
- Super admin creates new org: name, domain, plan, initial admin email
- System auto-sends invite email to initial admin
- On org creation: generate two API keys (production + staging)
- Org gets its own `org_id` — stamped on all their data from day one

#### 2.2 Row-level data isolation — CRITICAL
- `org_id` column on every data table (users, referrals, fraud_flags, reward_transactions, reward_config, campaigns)
- Every API query appends `WHERE org_id = :org_id` from the JWT
- No API parameter can override the token's org_id
- Database-level: add row-level security policies on PostgreSQL (belt-and-suspenders)
- Integration tests assert that org A cannot read org B's records under any condition

#### 2.3 Plan & limits management — IMPORTANT
- Plans: Free (1K users, depth 2), Pro (100K users, depth 5), Enterprise (unlimited)
- Per-org overrides settable by super admin: max_users, max_depth, api_rate_limit
- When org hits limit: claims return `429 Plan Limit Reached` with upgrade prompt
- Super admin can bump limits without changing plan (for trials, negotiations)

#### 2.4 API key management — IMPORTANT
- Each org has multiple named keys: "Production", "Staging", "CI"
- Key shown once on creation — hashed after that, never retrievable again
- Rotate: generate new key, old key has 24h grace period before invalidation
- Revoke: instant invalidation
- Last used timestamp — if a key hasn't been used in 90 days, warn the admin
- Per-key rate limit override

#### 2.5 Team member management — IMPORTANT
- Org admin invites colleagues by email → invite link sent → they set password on first login
- Assign role on invite: manager or analyst
- Remove member: sessions immediately revoked, access gone
- Invite history: who was invited, by whom, accepted / pending / expired

#### 2.6 Billing & usage — NICE TO HAVE
- Monthly referral claim count vs plan limit — bar chart
- Overage warnings at 80% and 95% of limit
- Stripe integration for subscription management
- Invoice history (download PDF)
- Usage export for finance team

---

### 3. Fraud Management

#### 3.1 Manual flag / unflag user — CRITICAL
- One-click flag button on user profile
- Required: reason note before flagging (free text, min 10 chars)
- Flagging a user: immediately stops reward propagation through that node
- Unflag: requires justification note — who unflagged, why, when — all logged in audit trail
- Cannot be done by analyst role
- Flagging is reversible; banning is permanent (separate action)

#### 3.2 Fraud review queue — CRITICAL
- High-risk claims (risk score > threshold, configurable per org) go into `pending` state
- Claim is not committed or rejected yet — held in `fraud_review_queue`
- Manager sees queue: referral details, risk score, reason, user history
- Actions: Approve (commit the edge + propagate rewards) or Reject (fraud flag + notify)
- Review note required on rejection
- SLA timer: queue items older than 24h get highlighted, older than 48h trigger a notification
- Audit trail: every approve / reject logged with reviewer ID

#### 3.3 Bulk actions on fraud flags — CRITICAL
- Checkbox selection on fraud flags table
- Bulk actions: Unflag selected, Block selected users, Export selected to CSV
- Used when a coordinated referral ring is detected — act on all of them at once
- Confirmation modal with count before executing bulk action

#### 3.4 Fraud rule configuration — IMPORTANT
- Edit per-org via UI form (no code deploy needed):
  - Velocity limit: max claims per user per minute / hour
  - Duplicate window: how long before same (child, parent) pair is considered duplicate
  - Risk score threshold for auto-reject vs queue for review
  - Custom blocklist: email domains, IP ranges
- Changes take effect immediately (hot-reload, no restart)
- Change history: every rule edit logged with before/after state
- "Test rule" button: run rule against last 100 claims and see what would have been flagged

#### 3.5 Fraud pattern visualiser — IMPORTANT
- Graph view overlay showing clusters of flagged users
- Flagged nodes rendered in red; suspicious edges in orange dashed lines
- Admin can see at a glance: are these flagged users connected? Is it a coordinated ring?
- Clicking a cluster zooms in and shows all edges within it
- Export cluster as report

#### 3.6 Fraud alert threshold configuration — IMPORTANT
- Set email / Slack / webhook alert when:
  - Fraud rate exceeds X% of total claims in last hour
  - More than N cycle attempts in last 10 minutes (potential coordinated attack)
  - Any single user exceeds Y velocity events
- Each org configures their own thresholds
- Alert channels: email, Slack webhook, in-app notification, PagerDuty (enterprise)
- Alert deduplication: don't send same alert more than once per 30 min

---

### 4. Reward Management

#### 4.1 Reward config editor — CRITICAL
- UI form to edit: max depth, reward type (fixed / percent), amounts per level
- Preview panel: shows projected payout for a sample 3-level chain before saving
- Save creates a new version (old config preserved, never deleted)
- Config version history: see all past configs, who changed them, when — and revert if needed
- Changes effective immediately for new claims; does not retroactively affect past transactions

#### 4.2 Manual reward adjustment — CRITICAL
- Credit or debit any user's reward balance from user profile
- Required fields: amount, direction (credit/debit), reason note
- Creates a `reward_transaction` row with type `manual_adjustment` and admin actor ID
- Full ledger preserved — balance is always derived from transactions, never just stored as a number
- Cannot be done by analyst or manager — org admin and above only

#### 4.3 Reward freeze / hold — IMPORTANT
- Freeze a specific user's pending rewards during fraud investigation
- Rewards continue to accumulate in the ledger but are flagged `frozen = true`
- User cannot withdraw or be paid out while frozen
- Unfreeze options on investigation resolution:
  - Release: all frozen rewards become payable immediately
  - Forfeit: all frozen rewards zeroed out with audit note
- Freeze / unfreeze logged in audit trail

#### 4.4 Campaign manager — IMPORTANT
- Create named campaign with: start time, end time, reward multiplier or full config override
- Target segment: all users, or filter by join date, referral count, region, user status
- Campaign preview: estimated cost based on current referral rate × campaign duration
- Multiple campaigns can overlap — system applies highest multiplier
- Campaign status: Draft → Scheduled → Active → Ended
- End early: cancel a live campaign (rewards already paid stay paid, new claims revert to base config)
- Campaign history with performance metrics: total claims, total payout, vs baseline

#### 4.5 Payout approval workflow — IMPORTANT
- Rewards above a configurable threshold (e.g. ₹500) require manager approval before being marked payable
- Approval queue: user, amount, referral that triggered it, reward level
- Approve: mark as payable — included in next payout batch
- Reject with note: reward voided, user notified
- Auto-approve below threshold to reduce queue noise
- SLA: items pending > 48h trigger notification to org admin

#### 4.6 Reward ledger export — NICE TO HAVE
- Export `reward_transactions` as CSV or Excel
- Filters: date range, user ID, campaign, reward type, status (frozen / payable / paid)
- Scheduled exports: daily CSV to org admin's email at 08:00
- Format compatible with standard accounting tools (Tally, Zoho Books)

---

### 5. Operations & User Management

#### 5.1 User search & profile — CRITICAL
- Search by: email, name, UUID, phone (if collected)
- Full user profile page in one view:
  - Status badge (active / flagged / suspended / banned)
  - Reward balance + full transaction history
  - Referral tree (3 levels up and down from this user)
  - All fraud flags with reasons and timestamps
  - All claims (valid and rejected) with timestamps
  - Audit log entries affecting this user
- Actions available from profile: flag, unflag, suspend, reinstate, manual reward adjust, freeze rewards

#### 5.2 Full audit log — CRITICAL
- Every admin action logged: actor, action, resource type, resource ID, before/after state, IP, timestamp
- Actions logged include: login, logout, flag, unflag, reward adjust, config change, campaign create/edit, webhook fire, org create, team member invite/remove, API key create/revoke
- Immutable: no admin can delete audit log entries, including super admin
- Searchable by: actor, action type, resource ID, date range, IP address
- Exportable as CSV
- Retained for minimum 2 years (compliance)

#### 5.3 User status management — IMPORTANT
- **Suspend**: blocks new referral claims, user still exists, history preserved. Reversible.
- **Reinstate**: lifts suspension, user can claim again
- **Permanent ban**: all claims blocked forever, user removed from reward propagation chain (ancestors still rewarded from other valid paths), history preserved for audit
- All status changes require reason note and are logged in audit trail
- Bulk suspend: select multiple users, suspend all with single action + shared reason note

#### 5.4 Notification centre — IMPORTANT
- In-app notification bell with unread count badge
- Notification types:
  - High fraud rate detected (> X% in last hour)
  - Reward config changed (who changed it, what changed)
  - Payout approval needed in queue
  - New team member joined
  - API key not used in 90 days (dormant key risk)
  - System health warning (DAG engine slow, DB lag)
  - Campaign about to expire (24h warning)
- Mark as read / mark all as read
- Email digest option: immediate / hourly summary / daily summary

#### 5.5 Webhook configuration — IMPORTANT
- Org admin sets their own webhook endpoint URLs
- Events available to subscribe to:
  - `referral.claimed` — new valid referral committed
  - `referral.rejected` — claim rejected with reason
  - `fraud.flagged` — user or claim flagged
  - `reward.paid` — reward credited to a user
  - `reward.frozen` — reward frozen during investigation
  - `campaign.started` — campaign went live
  - `campaign.ended` — campaign ended
- Payload signed with HMAC-SHA256 using per-webhook secret
- Test-fire button: sends sample payload to the URL and shows response
- Delivery log: every webhook attempt with status code, response body, timestamp
- Auto-retry: exponential backoff on failure (1 min → 5 min → 30 min → give up after 3 attempts)
- After 10 consecutive failures: webhook auto-disabled + admin notified

#### 5.6 Data export & GDPR tools — NICE TO HAVE
- Export all data for a specific user on request (GDPR Subject Access Request):
  - All referral records, reward transactions, fraud flags, audit entries
  - Delivered as ZIP with structured JSON files
  - Response within 72 hours (log request timestamp for compliance)
- Delete user data: anonymise rather than hard-delete (replace PII with `[DELETED]`, keep structural data for graph integrity)
- Consent log: when user accepted terms, what version, from what IP
- Data retention config: auto-anonymise inactive users after N years

---

### 6. Analytics & Reporting

#### 6.1 Referral funnel report — IMPORTANT
- Stages: Referral link generated → Link clicked → Claim submitted → Claim accepted → User retained (30 days)
- Drop-off percentage at each stage
- Filter by: campaign, date range, referral source
- Comparison mode: this period vs last period

#### 6.2 Top referrers leaderboard — IMPORTANT
- Ranked by: most referrals generated, most rewards earned, highest quality score (retention-weighted)
- Toggle time period: last 7 days / 30 days / all time
- Columns: rank, user (truncated UUID + email), referral count, rewards earned, quality score
- Export to CSV
- Click row to go to that user's profile

#### 6.3 Fraud rate trend chart — IMPORTANT
- Fraud attempts over time — daily and weekly granularity
- Breakdown by type: cycle blocked, velocity limit, self-referral, duplicate
- Overlay: total claims line so fraud rate (%) is visible, not just raw count
- Anomaly highlight: spikes automatically marked with a flag icon
- Date range selector

#### 6.4 Reward cost analytics — IMPORTANT
- Total rewards distributed per day / week / month
- Breakdown: level 1 vs level 2 vs level 3 payouts
- Cost per acquired user (total rewards ÷ new valid referrals)
- Campaign cost vs baseline cost comparison
- Projected monthly cost based on current referral rate

#### 6.5 Cohort retention analysis — NICE TO HAVE
- Of users referred in week X, what % are still active in week X+1, X+2, X+4, X+8?
- Measures referral quality, not just volume
- Compare cohorts across campaigns: did the Diwali campaign bring better-retained users?
- Export as CSV for external analysis

#### 6.6 DAG network health metrics — NICE TO HAVE
- Average tree depth across all users
- Distribution of tree widths (how many users has each referrer brought?)
- Orphan nodes (root users with no children) — potential to target with re-engagement
- Most connected nodes (super-referrers) — flag for influencer programme
- Graph density over time

---

## 🚀 Phased Build Order

### Phase 1 — Foundation (Week 1) — HARD BLOCKER

**Nothing else is safe to build until this is done.**

- [ ] Add `org_id` column to every existing table (migration)
- [ ] Create `organisations` table
- [ ] Create `admin_users` table
- [ ] Create `admin_sessions` table
- [ ] JWT auth: issue token with `user_id`, `org_id`, `role`
- [ ] `get_current_org` FastAPI dependency — injects `org_id` from token into every route
- [ ] All existing API routes updated to filter by `org_id`
- [ ] Login page (email + password)
- [ ] Protected route middleware on frontend
- [ ] Super admin: org CRUD (create, list, suspend)
- [ ] Fix: DAG Explorer graph canvas (wiring react-flow to API response)
- [ ] Fix: reward_config seed row (so rewards distribute correctly)
- [ ] Fix: UUID copy-to-clipboard in fraud monitor
- [ ] Fix: verify activity feed events are human-readable strings

### Phase 2 — Core Admin Features (Week 2)

- [ ] User search with full profile page
- [ ] Manual flag / unflag with reason note + audit log entry
- [ ] Reward config editor UI with preview panel
- [ ] Audit log viewer (filterable, exportable)
- [ ] Session management (view all sessions, revoke any)
- [ ] Password reset flow (email link)
- [ ] Team member invite + role assignment
- [ ] Create `audit_log` table and start writing to it on every admin action

### Phase 3 — Operations Layer (Week 3)

- [ ] Fraud review queue (pending / approve / reject workflow)
- [ ] Bulk actions on fraud flags table
- [ ] Fraud rule configuration UI (per-org, hot-reload)
- [ ] Campaign manager (create, schedule, monitor)
- [ ] Payout approval queue
- [ ] Webhook configuration + delivery log
- [ ] In-app notification centre
- [ ] Google OAuth / SSO login
- [ ] Fraud rate trend chart
- [ ] Top referrers leaderboard
- [ ] Reward cost analytics panel

### Phase 4 — Maturity (Later)

- [ ] Two-factor authentication (TOTP)
- [ ] Billing & usage panel (Stripe integration)
- [ ] SAML SSO for enterprise orgs
- [ ] GDPR data export + anonymisation tools
- [ ] Cohort retention analysis
- [ ] DAG network health metrics
- [ ] ML fraud scoring (risk score 0–1 on each claim)
- [ ] Fraud pattern visualiser (cluster view in graph)
- [ ] PagerDuty / Slack alert integration

---

## ⚠️ Non-Negotiable Security Rules

1. **`org_id` always comes from the verified JWT token** — never from a client-supplied query parameter or request body. If a client sends `?org_id=other-org`, it is silently ignored.

2. **Audit log is immutable** — no admin, including super admin, can delete or edit audit log entries. Append-only table with no DELETE or UPDATE grants.

3. **API keys stored as hashes** — the plaintext key is shown once on creation and never again. If lost, the admin must revoke and generate a new one.

4. **Passwords hashed with bcrypt** — never MD5 or SHA. Cost factor ≥ 12.

5. **Fraud review queue is transactional** — approve and commit-edge must be a single atomic DB transaction. If the commit fails, the approval is rolled back.

6. **Org isolation tested** — integration test suite must include cross-org access attempts and assert they all return 403.

7. **Super admin actions are extra-logged** — every super admin action (especially org CRUD and data access) written to a separate immutable `super_admin_audit_log` table.

---

## 📦 Updated Deliverables Checklist

### Already built (current build)
- [x] Working backend APIs (FastAPI, all referral endpoints)
- [x] Cycle detection logic (BFS, in-memory, < 100ms)
- [x] Metrics panel dashboard (6 stats)
- [x] Fraud monitor with reason badges
- [x] Activity feed with WebSocket (connected)
- [x] Seed data script
- [x] Dark theme UI

### Fixes needed now
- [ ] DAG Explorer graph rendering
- [ ] Rewards distributed (reward_config seed + propagation)
- [ ] UUID copy-to-clipboard in fraud monitor
- [ ] Activity feed event format (human-readable strings)

### Phase 1 additions
- [ ] Multi-tenancy (org_id migration)
- [ ] JWT auth system
- [ ] Login page
- [ ] RBAC on all routes

### Phase 2–4 (planned)
- [ ] All features listed in sections 1–6 above

---

*Last updated: March 2026*
*Review source: Admin dashboard screenshot analysis + architecture design session*
