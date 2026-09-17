# SME Connect — Module Breakdown

Modular design for the Unified Workflow Automation Platform. Each module lists purpose, key features, and suggested tech stack (primary pick + alternatives) — aligned to MERN where possible, given existing project background.

---

## Market Gap → Module Mapping

Every module below exists to close a specific, evidence-backed gap identified in research — not just to mirror what Zapier/Make/n8n already do. This table is the "why" behind the module list.

| Gap identified | Evidence | Module that closes it |
|---|---|---|
| SMEs don't know *where to start* with automation — overwhelm, not cost, is the top blocker | Indradhar; PayNearby (36% cite resistance to new tech) | **Module 3A: Onboarding & Template Library** |
| No SME-friendly self-hosted option exists — n8n is self-hostable but requires technical comfort; Zapier/Make/Zoho/Pabbly are all cloud-locked | Platform study (research.md) | **Module 10: Deployment Flexibility (Cloud + Self-Host)** |
| Indian SMEs run core workflows through WhatsApp, but no mainstream no-code platform treats it as a first-class citizen | Digiwah — WhatsApp is the first touchpoint in the typical SME data flow | **Module 11: WhatsApp / Regional Connector** |
| Task-based pricing (Zapier) is unpredictable and penalizes scale — SMEs can't budget for it | Zapier pricing research (research.md) | **Module 9: Flat, Predictable Billing** |
| LCNC platforms are criticized for vendor lock-in and poor exportability | Acta Economica, 2025 — 7 LCNC inhibitors | **Module 12: Workflow Export & Data Portability** |
| Non-technical users abandon tools with blank-canvas builders | Impact of No-Code on Product Dev (arXiv) | **Module 3: Workflow Builder**, paired with Module 3A |

---

## 1. User & Organization Management

**Purpose:** Foundation module — identity and permissions that every other module depends on.

**Key features:**
- Signup/login with email verification
- JWT-based authentication (access + refresh tokens)
- Organization/workspace creation (multi-tenant from day one)
- Role-based access control — Admin / Editor / Viewer
- Team invites via email link
- Audit trail of who changed what (login, workflow edits, permission changes)

**Suggested stack:**
- **Primary:** Node.js + Express, MongoDB (User, Organization, Membership collections), JWT (jsonwebtoken), bcrypt/argon2 for password hashing, Resend or Nodemailer for transactional email
- **Alternatives:** Auth0 or Clerk (managed auth, faster to build but less control/cost at scale), Ory Kratos (open-source, self-hostable identity — fits Module 10's self-host story well), PostgreSQL with row-level security instead of MongoDB if strict relational integrity across orgs is wanted

---

## 2. Connector / Integration Management

**Purpose:** Registry of supported external apps and the credentials needed to talk to them.

**Key features:**
- Supported-app registry (Google Sheets, one CRM, one billing tool, one accounting tool for v1)
- OAuth 2.0 credential storage, scoped per user/organization
- Standard connector interface (ports-and-adapters pattern) — new apps plug in as adapters without touching the core engine
- Connection health check / re-auth flow
- Generic "custom API" connector (like n8n's HTTP Request fallback) so unsupported apps aren't a dead end

**Suggested stack:**
- **Primary:** Node.js service layer with a common `Connector` interface (`connect()`, `fetchTrigger()`, `executeAction()` per adapter), MongoDB for encrypted credential storage, Passport.js or simple-oauth2 for OAuth flows
- **Alternatives:** HashiCorp Vault or AWS Secrets Manager for credential storage instead of encrypted MongoDB fields (stronger security story for the report), Nango or Unified.to (open-source unified-API layers built exactly for this — worth citing as a reference architecture even if not adopted directly)

---

## 3. Workflow Builder (No-Code UI)

**Purpose:** The module users interact with most — the visual trigger→action canvas. Worth the most UI/UX investment.

**Key features:**
- Drag-and-drop step builder (trigger + one or more actions)
- Field mapping UI between source and destination apps
- Condition/filter blocks (if X, then Y)
- Multi-step chaining and branching
- Save as draft / publish workflow
- Inline validation (flags broken mappings before publish, not after failure)

**Suggested stack:**
- **Primary:** React + React Flow (purpose-built node-graph library, industry standard for this exact use case), Tailwind CSS, Zustand for builder state, MongoDB storing the workflow definition as JSON (nodes + edges)
- **Alternatives:** Rete.js or Drawflow (lighter-weight node-editor libraries if React Flow feels heavy), tldraw (for a more freeform canvas feel), Redux Toolkit instead of Zustand if the team is more familiar with it

---

## 3A. Onboarding & Guided Template Library *(new — closes the #1 identified gap)*

**Purpose:** Directly targets the research finding that SMEs don't struggle with cost as much as with *not knowing where to start*. This is arguably SME Connect's biggest differentiator over Zapier/Make, which both hand new users a blank canvas.

**Key features:**
- Pre-built starter templates by common SME scenario (e.g. "New CRM lead → add to spreadsheet → draft invoice", "New WhatsApp enquiry → add lead to CRM")
- Guided setup wizard: pick your industry/use case → suggested workflows → one-click activate with just credential entry
- In-app checklist for first-time users ("Connect your first app", "Run your first workflow")
- Searchable template gallery, tagged by app and by business function (Sales / Billing / Inventory)

**Suggested stack:**
- **Primary:** Templates stored as static JSON workflow definitions in MongoDB, React wizard UI reusing Module 3's builder components in a locked-down "fill in the blanks" mode
- **Alternatives:** A lightweight recommendation layer (rule-based, not ML — e.g. "if user selected 'Retail' → show these 5 templates") is enough for v1; no need for a real ML recommender at this scope

---

## 4. Trigger & Event Detection Engine

**Purpose:** Detects when a workflow should run.

**Key features:**
- Webhook listener endpoint for apps that support real-time push
- Scheduled polling for apps that don't (configurable interval)
- Deduplication logic — prevents the same event firing a workflow twice
- Trigger payload normalization before handoff to the execution engine

**Suggested stack:**
- **Primary:** Express webhook routes, node-cron or BullMQ repeatable jobs for polling, Redis for a dedup/idempotency cache (store last-seen event IDs with TTL)
- **Alternatives:** Temporal (if the team wants to study a more robust, enterprise-grade workflow-orchestration engine — heavier than needed for v1 but a strong "future work" mention in the report), AWS EventBridge if going cloud-native instead of self-managed queues

---

## 5. Workflow Execution Engine

**Purpose:** The core orchestration layer — runs the defined trigger→action sequence.

**Key features:**
- Pulls trigger data, applies field mappings, calls destination app APIs
- Handles branching/conditional paths
- Async, queued execution (don't block on external API calls)
- Execution status tracking (queued/running/success/failed)
- Rate-limit awareness per connected app (avoid hitting third-party API caps)

**Suggested stack:**
- **Primary:** BullMQ + Redis for the task queue (Node-native equivalent of Zapier's Celery/RabbitMQ setup studied in the architecture research), worker processes separate from the API server, MongoDB for execution records
- **Alternatives:** RabbitMQ directly (closer to what Zapier actually uses, stronger citation match if the report leans on that comparison), AWS SQS + Lambda if going serverless for the worker layer (mirrors Zapier's Lambda isolation pattern from your architecture study)

---

## 6. Error Handling, Logging & Retry

**Purpose:** Trust layer — silent failures are the #1 trust-breaker for this category of product.

**Key features:**
- Capture failed runs with full error context
- Retry with exponential backoff (configurable max attempts)
- Full execution log per workflow run (timestamp, payload, status, error if any)
- Dead-letter handling for workflows that exhaust retries
- Plain-language error messages for non-technical users (not raw API error codes)

**Suggested stack:**
- **Primary:** BullMQ's built-in retry/backoff support, MongoDB collection for structured logs (indexed by workflowId + timestamp), Winston or Pino for service-level logging
- **Alternatives:** Sentry (error tracking/alerting, free tier is generous and demos well), ELK stack (Elasticsearch + Logstash + Kibana) if the report wants to show a more enterprise-grade observability story

---

## 7. Monitoring Dashboard & Notifications

**Purpose:** Where users go to see (and trust) that their automations are working.

**Key features:**
- Workflow status overview (active/paused/error)
- Run history with success/failure rates
- Email or in-app notification when a workflow fails repeatedly
- Basic usage stats (tasks run this month, per workflow)

**Suggested stack:**
- **Primary:** React dashboard consuming a REST/GraphQL API, Recharts or Chart.js for run-history visualizations, Nodemailer/Resend + a notification-preferences model for alerts
- **Alternatives:** GraphQL (Apollo Server) instead of REST if the dashboard needs flexible, nested queries; Socket.io for live status updates instead of polling the API on an interval

---

## 8. Data Mapping & Transformation Layer

**Purpose:** Handles the schema differences between source and destination apps — where most real-world integration bugs live.

**Key features:**
- Field-to-field mapping (e.g. CRM `full_name` → Sheet `Name` column)
- Basic transformations: formatting, concatenation, default values, type coercion
- Mapping validation before a workflow can be published

**Suggested stack:**
- **Primary:** A small transformation-function library in Node (pure functions, unit-testable), mapping config stored as part of the workflow JSON in MongoDB, JSON Schema for validating mapped output shape
- **Alternatives:** JSONata or JMESPath (declarative JSON transformation languages — lets power users write custom mapping expressions later without you building a full expression engine yourself)

---

## 9. Flat, Predictable Billing & Subscription *(reframed — closes the pricing-complexity gap)*

**Purpose:** Zapier's task-based metering is a documented pain point — costs balloon unpredictably as usage grows, which is exactly what budget-constrained SMEs can't tolerate. SME Connect's differentiator here is a flat, workflow-count-based (not task-count-based) pricing model that's easy for a non-technical owner to understand and budget for.

**Key features:**
- Tiered plans based on **number of active workflows**, not number of executions — removes the "surprise bill" problem
- Usage dashboard showing plan limits clearly (not buried in fine print)
- Simple upgrade/downgrade flow, no sales call required

**Suggested stack:**
- **Primary:** Stripe (test mode is fine for an academic demo) with a plan/usage schema in MongoDB
- **Alternatives:** A fully mocked billing service (plan/usage collections, no real payment gateway) is defensible for a purely academic submission if Stripe integration eats into time better spent on Modules 3-6

---

## 10. Deployment Flexibility — Cloud + Self-Host *(new — closes the self-hosting gap)*

**Purpose:** Across the whole platform study, **n8n is the only self-hostable option**, and even that requires real technical comfort to deploy and maintain. Every SME-friendly competitor (Zapier, Make, Zoho Flow, Pabbly) is cloud-only. For SMEs with data-residency concerns, compliance requirements, or a general reluctance to put business data on third-party servers, there is no accessible self-hosted option. SME Connect can own this gap by offering a genuinely easy self-host path alongside the default cloud SaaS.

**Key features:**
- Default: multi-tenant cloud SaaS (as with every other module above)
- Optional: single-command self-hosted deployment for SMEs that want data on their own infrastructure
- Config-driven environment setup (no manual database/queue setup required)

**Suggested stack:**
- **Primary:** Docker + Docker Compose bundling the API, worker, MongoDB, and Redis into one `docker-compose up` deployment — this is the actual "doable" version of self-hosting for a non-technical SME, unlike n8n's more DIY setup
- **Alternatives:** Kubernetes Helm chart (more scalable but overkill and too technical for the target user — worth mentioning as a "future work: enterprise self-host" note rather than building it), Railway/Render one-click deploy templates as a middle ground between full self-host and pure SaaS

---

## 11. WhatsApp / Regional Connector *(new — closes a specific Indian-SME gap)*

**Purpose:** Research shows the typical Indian SME data flow *starts* on WhatsApp (customer enquiry → manually copied into a spreadsheet → re-entered into CRM). No mainstream no-code platform treats WhatsApp as a first-class trigger/action node — it's either unsupported or buried behind a generic webhook that a non-technical user can't configure alone.

**Key features:**
- WhatsApp Business API as a first-class trigger ("New message received") and action ("Send message/template")
- Pre-built template pairing this with Module 3A (e.g. "New WhatsApp enquiry → create CRM lead")
- Basic template-message support (WhatsApp Business API requires pre-approved templates for outbound messages — worth noting as a real constraint in the report)

**Suggested stack:**
- **Primary:** WhatsApp Business Platform API (Meta Cloud API — free tier available, no need for a paid BSP for an academic build), Node.js webhook handler feeding into Module 4
- **Alternatives:** Twilio's WhatsApp API (easier onboarding than Meta's raw Cloud API, small per-message cost) if Meta's app-review process is too slow for the project timeline

---

## 12. Workflow Export & Data Portability *(new — closes the vendor lock-in gap)*

**Purpose:** LCNC platforms are consistently criticized in the literature for vendor lock-in — once a business builds workflows on a platform, leaving means rebuilding everything from scratch. Addressing this directly is a low-effort, high-credibility addition to the report.

**Key features:**
- Export any workflow as a portable JSON file (nodes, edges, mappings — credentials excluded for security)
- Import a previously exported workflow back in (supports backup, and duplication across workspaces)
- Human-readable workflow documentation auto-generated from the definition (what triggers what, in plain English)

**Suggested stack:**
- **Primary:** JSON serialization of the existing workflow schema (Module 3 already stores workflows this way — this module is mostly an export/import UI + validation layer on top)
- **Alternatives:** None needed — this is intentionally lightweight; over-engineering it would be a poor use of project time relative to its role in the report

---

## Suggested Build Priority

For a major project demo, prioritize in this order:

1. **Modules 1 & 2** — foundation, needed before anything else works
2. **Module 3 + 3A** — the centerpiece; template-driven onboarding is your strongest differentiator and most convincing demo moment
3. **Modules 4, 5, 6** — the core engine; this is where your Zapier/Zoho architecture research directly applies
4. **Modules 7 & 8** — round out data quality and user trust
5. **Module 11 (WhatsApp)** — high-impact, India-specific differentiator; strong to include if time allows, since it's a genuinely novel angle vs. every competitor studied
6. **Module 12 (Export/Portability)** — cheap to build once Module 3's schema exists; good "we thought about lock-in" credibility for relatively little effort
7. **Module 10 (Self-Host)** — valuable as a *design and Docker Compose proof-of-concept* even if not fully productionized; demonstrate the concept rather than building enterprise-grade deployment tooling
8. **Module 9 (Billing)** — design-only or Stripe test-mode is acceptable; don't let it compete for time against the core engine