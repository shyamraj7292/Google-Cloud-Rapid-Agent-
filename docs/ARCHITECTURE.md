# Copa Agent — Architecture

Copa Agent is a true action-taking agent built on Google Cloud and the Model
Context Protocol (MCP). The defining design principle: **every integration has a
real path and a same-shape fallback**, so the agent degrades gracefully instead
of breaking.

## System diagram

```
┌─────────────────────────────┐
│  Web Dashboard (frontend/)  │   live action feed + engine-mode badge
│  vanilla HTML/CSS/JS        │
└──────────────┬──────────────┘
               │ POST /api/agent/chat/stream  (Server-Sent Events)
               ▼
┌─────────────────────────────┐
│  FastAPI backend (Cloud Run)│   routes/agent.py · webhooks.py · dashboard.py
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  AgentService  — reason → act → observe loop                 │
│  backend/services/agent_service.py                           │
│                                                              │
│  backend = vertex │ gemini │ scripted   (auto-selected)      │
└───────┬───────────────┬───────────────────┬─────────────────┘
        ▼               ▼                   ▼
 GitLabToolExecutor  GroundingService   MemoryService
 (gitlab_tools.py)   (grounding_*.py)   (memory_service.py)
        │               │                   │
   GitLab MCP /     Vertex AI Search /   Firestore /
   python-gitlab    local runbooks       in-memory
   ── or sim ──     ── or local ──       ── or local ──
```

## Components

### 1. AgentService — the brain (`backend/services/agent_service.py`)
Runs a bounded **reason → act → observe** loop (max 10 steps). It decides which
tool to call, the tool executes for real, the result is fed back, and it
continues until the task is done. Three interchangeable backends, all emitting an
identical event stream:

- **`vertex`** — Vertex AI (`google-cloud-aiplatform`) function calling. Selected
  when a full GCP project is configured. The enterprise/sponsor path.
- **`gemini`** — `google-generativeai` function calling with an API key.
- **`scripted`** — a deterministic planner used when no LLM is available. It still
  performs the **real tool calls** end-to-end, guaranteeing the demo always works.

### 2. GitLabToolExecutor (`backend/services/gitlab_tools.py`)
The single source of truth for every GitLab action: `list_pipelines`,
`list_pipeline_jobs`, `get_pipeline_job_log`, `get_file_contents`,
`create_branch`, `create_or_update_file`, `create_merge_request`, `create_issue`,
`run_pipeline`, `get_platform_status`.

- **LIVE**: real calls via `python-gitlab` (and the GitLab MCP server in the
  Agent Builder configuration under `agent/`).
- **SIMULATION**: a self-consistent in-memory model of the platform, seeded with
  the planted `TOKEN_EXPIRY_SECONDS = 360` bug and real job logs. Committing the
  fix flips the simulated pipeline to green — so the workflow is provably correct
  with zero cloud setup.

### 3. GroundingService (`backend/services/grounding_service.py`)
Retrieval over the team's runbooks/playbooks so fixes are **grounded and cited**.
Uses **Vertex AI Search** (Discovery Engine) when a data store is configured,
otherwise an in-process keyword index over `agent/datastores/*.md`. Returns
citations (`source › section`) that the agent surfaces in its reply.

### 4. MemoryService (`backend/services/memory_service.py`)
Per-session conversation history in Firestore, with an in-memory fallback.

### 5. Web dashboard (`frontend/`)
Dark command-center UI. Consumes the SSE stream to render the agent's live
"thinking" and each tool action into the activity timeline as it happens. Shows
the active engine mode as a nav badge.

## Walkthrough: "fix the failing pipeline"

1. Dashboard POSTs the message to `/api/agent/chat/stream`.
2. AgentService starts the loop and emits `status`/`action` events over SSE.
3. `list_pipelines` → finds pipeline #42 **failed**.
4. `list_pipeline_jobs` → `unit_test` is the failing job.
5. `get_pipeline_job_log` → reads the `AssertionError` (expected 3600, got 360).
6. `search_runbooks` → grounds in *Pipeline Playbooks › Unit Test Failures*.
7. `get_file_contents` → reads `app/main.py`.
8. `create_branch` → `fix/auth-token-expiry`.
9. `create_or_update_file` → commits `TOKEN_EXPIRY_SECONDS = 3600`.
10. `create_merge_request` → opens MR **!18** with a root-cause writeup.
11. `run_pipeline` → re-runs on the fix branch → **success**.
12. Final `reply` summarizes the fix, links the MR, and cites the playbook.

Every step streams to the dashboard as it occurs.
