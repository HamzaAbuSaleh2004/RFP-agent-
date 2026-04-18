# LiverX RFP Agent — Full Workflow Reference

_Last revised: 2026-04-18_

This document captures the end-to-end workflow of the LiverX RFP management application: the page routes, API surface, agent topology, RFP lifecycle, integrations, UI structure, and typical user journeys. It is the canonical "what does this app actually do and how does it hang together" reference.

---

## 1. High-Level Architecture

**Stack**

- **Backend:** FastAPI (Python), Jinja2 templates, Uvicorn.
- **AI layer:** Google ADK (Agent Development Kit) — `Runner` + `InMemorySessionService` — orchestrating a small multi-agent system.
- **Persistence:** JSON file at [data/rfps.json](data/rfps.json) (single source of truth for RFPs, bids, evaluations, and lifecycle state).
- **Frontend:** Server-rendered Jinja templates styled with Tailwind (CDN) + Material Design tokens. No SPA framework.
- **Streaming:** Server-Sent Events (SSE) for both the RFP chat and the general Assistant.
- **Integrations:** Slack (real, via MCP), Google Drive (real, via Python Drive API), FMP (mock vendor benchmarking), Jira (mock issue creation).

**Key files**

- [rfp_agent/main.py](rfp_agent/main.py) — FastAPI app, all routes, SSE endpoints, lifecycle hooks.
- [rfp_agent/agent.py](rfp_agent/agent.py) — agent definitions: `root_agent`, `rfp_creator`, `bid_evaluator`, `general_assistant`.
- [rfp_agent/rfp_store.py](rfp_agent/rfp_store.py) — RFP CRUD + lifecycle state machine.
- [rfp_agent/mcp_bridge.py](rfp_agent/mcp_bridge.py) — Slack, Jira (mock), Drive bridge functions.
- [rfp_agent/custom_tools.py](rfp_agent/custom_tools.py) — ADK tool wrappers used by the agents.
- [rfp_agent/pdf_engine.py](rfp_agent/pdf_engine.py) — markdown-to-PDF rendering for RFP documents.
- [rfp_agent/templates/](rfp_agent/templates/) — Jinja templates (all share `_sidebar.html` + `_topbar.html`).

---

## 2. Page Routes (HTML)

All pages share the unified shell: `_sidebar.html` (left nav) + `_topbar.html` (search + locale + user). Each page sets `{% set active_nav = '<key>' %}` to light up its sidebar entry.

| Route                | Template              | `active_nav`   | Purpose                                                             |
| -------------------- | --------------------- | -------------- | ------------------------------------------------------------------- |
| `/`                  | `dashboard.html`      | `dashboard`    | KPIs, recent RFPs, stats overview.                                  |
| `/create`            | `create.html`         | `create`       | "New RFP" form — title, description, language, invited users.       |
| `/chat`              | `rfp_creator.html`    | `documents`    | Agent-driven RFP drafting workspace (SSE chat + live PDF preview).  |
| `/documents`         | `documents.html`      | `documents`    | RFP list (drafts, published, archived toggle).                      |
| `/evaluations`       | `evaluations.html`    | `evaluations`  | Card grid of published/approved RFPs with evaluation summaries.     |
| `/settings`          | `settings.html`       | `settings`     | Org profile, integrations, legal guidelines editor.                 |
| `/editor/{rfp_id}`   | `editor.html`         | `documents`    | Split-pane markdown editor + PDF preview. Status-aware controls.    |
| `/assistant`         | `assistant.html`      | `assistant`    | Standalone general-Q&A chat powered by `general_assistant`.         |
| `/flowchart`         | `flowchart.html`      | (n/a)          | Visual architecture / workflow diagram.                             |

---

## 3. API Endpoints

### 3.1 RFP Resource

| Method | Path                                    | Description                                                 |
| ------ | --------------------------------------- | ----------------------------------------------------------- |
| POST   | `/api/rfps`                             | Create an RFP (status `draft`).                             |
| GET    | `/api/rfps`                             | List active RFPs (excludes archived by default).            |
| GET    | `/api/rfps/{id}`                        | Fetch one RFP.                                              |
| PATCH  | `/api/rfps/{id}`                        | Update title/description/status/content/etc.                |
| DELETE | `/api/rfps/{id}`                        | Hard delete (rare — prefer archive).                        |
| POST   | `/api/rfps/{id}/archive`                | Archive the RFP (sets `status='archived'`).                 |
| GET    | `/api/rfps/archived/list`               | List archived RFPs.                                         |
| POST   | `/api/rfps/{id}/regenerate-pdf`         | Re-render PDF from current `rfp_content` markdown.          |

### 3.2 Bids & Evaluation

| Method | Path                                      | Description                                                         |
| ------ | ----------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/api/rfps/{id}/bids`                     | List bids submitted for an RFP.                                     |
| POST   | `/api/rfps/{id}/bids`                     | Append a bid (auto-assigns uuid + `submitted_at`).                  |
| GET    | `/api/rfps/{id}/evaluation`               | Retrieve stored evaluation payload.                                 |
| GET    | `/api/rfps/{id}/risk-heatmap`             | Retrieve stored risk heat-map.                                      |
| GET    | `/api/evaluations`                        | Aggregate evaluation summaries for the grid page.                   |
| GET    | `/api/risk-heatmap`                       | Cross-RFP risk overview.                                            |
| POST   | `/api/extract-bid-text`                   | Extract text from an uploaded bid PDF before submission.            |

### 3.3 Chat (SSE)

| Method | Path                        | Description                                                                                                |
| ------ | --------------------------- | ---------------------------------------------------------------------------------------------------------- |
| POST   | `/api/chat`                 | RFP-scoped streaming chat (`rfp_id` + `session_id`). Drives `rfp_director` → `rfp_creator`/`bid_evaluator`. |
| POST   | `/api/assistant/chat`       | General Q&A stream (`general_<random>` session). Drives `general_assistant`.                               |

Both endpoints emit SSE events of shape `{type: 'chunk'|'status'|'done'|'error', text: ...}`.

### 3.4 Platform

| Method | Path                            | Description                                                               |
| ------ | ------------------------------- | ------------------------------------------------------------------------- |
| GET    | `/api/stats`                    | Dashboard KPIs (counts by status, etc.).                                  |
| GET    | `/api/search?q=...`             | Top-bar search across RFP titles/descriptions/content.                    |
| GET    | `/api/integrations`             | Configured/enabled status for Slack, Drive, FMP, Jira.                    |
| GET    | `/api/i18n/{locale}`            | Localized string bundle for client-side lookups.                          |
| GET    | `/api/settings/guidelines`      | Fetch legal/compliance guideline markdown.                                |
| PUT    | `/api/settings/guidelines`      | Save legal/compliance guideline markdown.                                 |

---

## 4. RFP Lifecycle (State Machine)

Defined in [rfp_agent/rfp_store.py](rfp_agent/rfp_store.py).

```
    ┌──────────┐
    │  draft   │◀──────────┐ rollback (PATCH status=draft)
    └────┬─────┘           │
         │ publish          │
         ▼                  │
    ┌──────────┐            │
    │published │────────────┘
    └────┬─────┘
         │ approve for submission
         ▼
 ┌──────────────────────┐
 │approved_for_submission│
 └────────┬─────────────┘
          │ mark done
          ▼
      ┌──────┐
      │ done │
      └──┬───┘
         │ archive
         ▼
     ┌───────────┐
     │ archived  │   (terminal)
     └───────────┘
```

**Valid statuses:** `draft`, `published`, `approved_for_submission`, `done`, `archived`.

**Legal transitions** (enforced — `patch_rfp` raises `ValueError` otherwise):

| From                      | To                                                        |
| ------------------------- | --------------------------------------------------------- |
| `draft`                   | `published`, `archived`                                   |
| `published`               | `approved_for_submission`, `draft` (rollback), `archived` |
| `approved_for_submission` | `done`, `archived`                                        |
| `done`                    | `archived`                                                |
| `archived`                | — (terminal)                                              |

**Legacy migration:** `{"approved": "published"}` — older records are remapped on read.

---

## 5. Agent Topology

```
            ┌─────────────────────────┐
  /chat ──▶ │   rfp_director (root)   │   ROUTER ONLY — never drafts
            │   sub_agents: ↓         │
            └──────┬──────────┬───────┘
                   │          │
                   ▼          ▼
           ┌──────────────┐  ┌────────────────┐
           │ rfp_creator  │  │ bid_evaluator  │
           └──────────────┘  └────────────────┘

  /assistant ──▶ general_assistant   (standalone; system-wide Q&A)
```

### 5.1 `rfp_director` (root)

- **Role:** Router. Reads the conversation, maps user input to one of the two sub-agents, transfers control.
- **Hard rules:**
  - _"You are a ROUTER ONLY. You MUST NOT draft the RFP yourself."_
  - Route to `rfp_creator` when user is providing info across the 5 categories: Scope, Vendor Reqs, Eval Criteria, Budget, Submission.
  - Route to `bid_evaluator` when bids are being evaluated / compared.
  - **HARD STOP:** no text-only handoff acknowledgements ("Sure, handing off to…"). Transfer must actually occur.
- **Backend kick-start:** if transfer fires but the sub-agent emits zero tokens, [main.py](rfp_agent/main.py) injects an automatic kick message so the sub-agent starts producing output.

### 5.2 `rfp_creator`

Drafts, audits, PDFs, and notifies. 8-step execution sequence:

1. Load local templates + current date.
2. FMP benchmark for vendor/market context (mock).
3. Legal alert to `#legal` on Slack.
4. Draft the RFP markdown.
5. Self-audit against three checklists: Legal, Compliance, Economic.
6. Present the draft to the user.
7. Generate the PDF via `create_rfp_pdf`.
8. Post a Slack update to `#updates`.

**Auto-save hook:** when `create_rfp_pdf` fires, the backend persists the generated markdown into `rfp.rfp_content` (with regex fallback for recovery from streamed text).

### 5.3 `bid_evaluator`

4-dimension evaluation framework: Legal, Commercial, Technical (0–100 score), Financial.

**Mandatory terminating tool chain:** `risk_heatmap` → `store_evaluation_results`.

**Auto-save hook:** when `store_evaluation_results` fires, the backend persists the payload into `rfp.evaluation`.

### 5.4 `general_assistant`

System-wide Q&A. Tools:

- `list_all_rfps`
- `get_rfp_summary`
- `read_local_templates`
- `gdrive_search` / `gdrive_read_file`
- `date_time`

No RFP-specific session scope — used by `/assistant`.

---

## 6. Integrations Matrix

Status returned by `/api/integrations`:

| Integration   | Real/Mock | Configured? (default)                     | Notes                                                                 |
| ------------- | --------- | ----------------------------------------- | --------------------------------------------------------------------- |
| Slack         | Real      | Env-driven (token + MCP server)            | Channels: legal `C0ARWKER0G4`, finance `C0ASMA9B33J`, updates `C0ASMLBU3TK`. |
| Google Drive  | Real      | Env-driven (Python Drive API, not MCP)     | `gdrive_search`, `gdrive_read_file`.                                  |
| FMP           | Mock      | Always configured (mock responses)         | Vendor benchmarking during drafting.                                  |
| Jira          | Mock      | Not configured (mock responses)            | `jira_create_issue`. Replaced Linear+Airtable tiles in the UI.        |

---

## 7. User Journeys

### 7.1 Create → Publish → Archive

1. User clicks **New RFP** on the dashboard → routed to `/create`.
2. Fills title/description/language/invitees → `POST /api/rfps` → record created with `status='draft'` → redirect to `/chat?rfp_id=…`.
3. On `/chat`, SSE chat drives `rfp_director`, which transfers to `rfp_creator`. The user supplies info across the 5 categories. The agent drafts, audits, generates the PDF (auto-saving `rfp_content`), and posts a Slack update.
4. User opens `/editor/{id}` to fine-tune the markdown; save regenerates the PDF.
5. User clicks **Publish** → `PATCH /api/rfps/{id}` with `status='published'`. Rollback is available (`published → draft`) while no bids are locked.
6. Vendors submit bids (`POST /api/rfps/{id}/bids`). When ready, user moves status to `approved_for_submission`, then `done`.
7. Done RFPs can be archived (`POST /api/rfps/{id}/archive`) and are hidden from the default list.

### 7.2 Evaluate Bids

1. User navigates to `/evaluations` — card grid of published/approved RFPs.
2. Opens an RFP's evaluation view. SSE chat drives `rfp_director` → `bid_evaluator`.
3. Agent scores each bid across Legal/Commercial/Technical/Financial, calls `risk_heatmap`, then `store_evaluation_results`.
4. Backend persists the evaluation + risk heat-map onto the RFP record; the UI re-renders from `/api/rfps/{id}/evaluation` and `/api/rfps/{id}/risk-heatmap`.

### 7.3 General Q&A

1. User opens `/assistant` (sidebar entry).
2. `general_assistant` handles the question using Drive search, local templates, RFP summaries, and date tools.
3. Session ID is `general_<random>` — unscoped to any specific RFP.

---

## 8. Data Model — RFP Record

Stored as a list of objects in [data/rfps.json](data/rfps.json):

| Field            | Type      | Notes                                                                 |
| ---------------- | --------- | --------------------------------------------------------------------- |
| `id`             | string    | UUID.                                                                 |
| `title`          | string    |                                                                       |
| `description`    | string    |                                                                       |
| `language`       | `en`/`ar` | Drives RTL and agent system-prompt language directives.               |
| `created_by`     | string    |                                                                       |
| `invited_users`  | list      | Email addresses / user identifiers.                                   |
| `status`         | enum      | One of the 5 lifecycle states.                                        |
| `assigned_vendor`| string    | Winning vendor after award.                                           |
| `rfp_content`    | markdown  | Canonical RFP body; source for PDF regeneration.                      |
| `evaluation`     | object    | Set by `store_evaluation_results`.                                    |
| `risk_heatmap`   | object    | Set by `risk_heatmap` tool.                                           |
| `bids`           | list      | Each bid: `{id, vendor, submitted_at, …}`.                             |
| `archived_at`    | timestamp | Set on archive.                                                       |
| `created_at`     | timestamp |                                                                       |
| `updated_at`     | timestamp |                                                                       |

---

## 9. UI Unification

**Shared partials**

- [rfp_agent/templates/_sidebar.html](rfp_agent/templates/_sidebar.html) — left nav. Reads `active_nav` to highlight the current entry.
- [rfp_agent/templates/_topbar.html](rfp_agent/templates/_topbar.html) — search + locale toggle + user avatar. Contains the client-side `/api/search` typeahead and the **Gemini 4-point star** gradient logo (`#4285F4 → #7B6EE0 → #9168C0`).

**`active_nav` values:** `dashboard`, `create`, `documents`, `evaluations`, `settings`, `assistant`.

**Layout convention:** every page uses `class="ml-64 …"` on its `<main>` to offset the fixed sidebar; topbar is sticky under the viewport top.

---

## 10. Internationalization (i18n)

- **Locales:** `en`, `ar`.
- **Detection:** `ui_lang` cookie; defaults to `en`.
- **RTL:** `rtl = (locale == 'ar')` is passed to every template. Each template's `<style>` block has inline Jinja directives that flip margins (`.ml-64` → `margin-right`), aside positioning, and chat-bubble alignment. Cairo font is loaded alongside Inter when RTL is active.
- **Agent language:** when `rfp.language == 'ar'`, [main.py](rfp_agent/main.py) prepends a system directive to the first user message in the SSE chat instructing the agent to respond in Arabic.
- **Client strings:** `/api/i18n/{locale}` returns a JSON bundle for dynamic pieces (top-bar placeholder, nav labels, etc.).

---

## 11. SSE Chat Mechanics

Both `/api/chat` and `/api/assistant/chat`:

1. Open a `Runner` session against the appropriate agent with the user's `session_id`.
2. Stream ADK events; for each text chunk → emit `{type:'chunk', text:…}`.
3. Emit `{type:'status', text:…}` on agent transfers and tool invocations.
4. On `done`, emit `{type:'done'}`.

**RFP-chat extras:**

- If a transfer to a sub-agent fires but the sub-agent produces zero tokens, the server injects an automatic kick message (`kick_text`) to nudge it into responding — this avoids the stuck "handoff silence" bug.
- When `create_rfp_pdf` tool fires → auto-save markdown to `rfp.rfp_content`.
- When `store_evaluation_results` fires → auto-save payload to `rfp.evaluation`.
- Regex fallbacks recover content from streamed text if the structured tool result is unavailable.

---

## 12. Quick-Start (dev)

```bash
# install
pip install -r requirements.txt

# run
uvicorn rfp_agent.main:app --reload

# smoke test imports
python -c "from rfp_agent import agent, main, mcp_bridge, custom_tools"
```

Environment variables (see `.env`):

- `GOOGLE_API_KEY` — Gemini / ADK.
- `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID` — Slack MCP.
- `GDRIVE_*` — Google Drive OAuth credentials.

---

## 13. Status (2026-04-18)

- All pages unified around `_sidebar.html` + `_topbar.html`.
- Gemini 4-point-star logo live in topbar search.
- Evaluations PUBLISHED badge centered inside the decorative grove.
- Phases 4–7 (Settings, bilingual UI, inline editor, FMP mock) complete.
- Jira replaces the Linear+Airtable tiles on `/chat`; integration status synced via `/api/integrations`.
- `/assistant` page live with SSE streaming against `general_assistant`.
