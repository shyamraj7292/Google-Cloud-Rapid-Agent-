# ⚽ Copa Agent — Autonomous DevOps Commander for World Cup 2026

**Built for the "Building Agents for Real-World Challenges" Hackathon (GitLab Track)**

## 🌐 Live Demo

**https://copa-agent-256475641367.us-central1.run.app**

Deployed on Google Cloud Run, running live against real GitLab projects via MCP,
grounded by Vertex AI Search, powered by Gemini 2.0 Flash.

Copa Agent is a true **action-taking AI agent** — not a chatbot — that acts as an
autonomous DevOps co-pilot for the teams building the infrastructure behind the
2026 FIFA World Cup (48 teams, 104 matches, 16 venues across 3 countries).

It runs a real **reason → act → observe loop**: when a pipeline breaks, Copa Agent
reads the CI logs, grounds itself in your team's runbooks, **writes the actual
code fix**, opens a Merge Request, and re-runs the pipeline to prove it's green —
all streamed to a live command-center dashboard, step by step.

> Powered by **Google Cloud (Gemini 2.0 Flash / Vertex AI Search)** and the **GitLab MCP server**.

---

## 🌟 What makes it different

Most "agents" describe what they *would* do. Copa Agent **does it**:

| Capability | What actually happens |
|---|---|
| 🔍 **Pipeline triage & auto-fix** | Lists pipelines → finds the failed job → reads the log → **commits the corrected file to a `fix/` branch → opens an MR → re-runs the pipeline** and reports green. |
| 📖 **Grounded, cited decisions** | Before acting, it searches your runbooks/playbooks (Vertex AI Search) and **cites the exact section it followed** — auditable, not guesswork. |
| 🚀 **Match Day deploy orchestration** | A multi-repo workflow that verifies **every** service is green before deploying — and *holds the deploy* with named blockers when one isn't. |
| 📝 **Issue → MR automation** | Turns a feature request into a real issue + branch + files + linked MR. |
| 📡 **Autonomous webhook triage** | A GitLab `pipeline failed` webhook makes the agent fix the bug with **zero human input**. |
| 🖥️ **Live reasoning UI** | Every tool call streams to the dashboard over SSE as the agent works. |

## 🛡️ Built to never die on stage: dual-mode by design

Every external integration has a real path **and** a high-fidelity fallback that
returns the *identical* data shape — so a missing credential degrades gracefully
instead of breaking the demo:

| Layer | Live mode | Fallback mode |
|---|---|---|
| **Agent brain** | Vertex AI / Gemini **function calling** | Deterministic planner that still runs the **real tool calls** end-to-end |
| **GitLab actions** | `python-gitlab` against gitlab.com (real MRs) | Stateful in-memory simulation where the fix genuinely turns the pipeline green |
| **Grounding** | Vertex AI Search data store | In-process keyword search over the local runbooks |
| **Memory** | Firestore | In-memory store |

The active mode is shown live as a badge in the dashboard nav. Drop in a token →
it upgrades automatically, no code change.

## 🏗️ Architecture

```
Browser dashboard ──SSE──▶ FastAPI backend ──▶ AgentService (reason→act→observe loop)
   (live action feed)         (Cloud Run)            │
                                                     ├─▶ GitLabToolExecutor  → GitLab (MCP / API)
                                                     ├─▶ GroundingService    → Vertex AI Search / runbooks
                                                     └─▶ MemoryService       → Firestore / in-memory
```

- **Agent loop**: `backend/services/agent_service.py` — Gemini/Vertex function calling + scripted planner
- **GitLab actions**: `backend/services/gitlab_tools.py` — branches, commits, MRs, issues, pipeline runs
- **Grounding**: `backend/services/grounding_service.py` — cited runbook retrieval
- **Streaming API**: `POST /api/agent/chat/stream` (SSE), `GET /api/agent/mode`
- **Frontend**: `frontend/` — dark command-center dashboard (vanilla HTML/CSS/JS)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the detailed flow.

## 🚀 Quick start

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# (Optional) configure live credentials — works fully without them
cp ../.env.example ../.env

# Run it
python -m uvicorn main:app --reload --port 8137
```

Open **http://localhost:8137** and try a quick action, or type:
> *"The ticketing API pipeline is failing — investigate and fix it."*

Watch the agent triage, fix, open MR **!18**, and turn the pipeline green — live.

### Going live (optional)
Set these in `.env` to upgrade from simulation to real services:
- `GITLAB_PERSONAL_ACCESS_TOKEN` + `GITLAB_GROUP_PATH` → real branches/MRs on gitlab.com
- `GOOGLE_CLOUD_PROJECT` (+ ADC) → Vertex AI agent brain
- `VERTEX_SEARCH_DATASTORE_ID` → Vertex AI Search grounding

## ✅ Tests

```bash
cd backend && pytest tests/ -v      # 12 tests, all green, no credentials needed
```

Includes the headline guarantee (`test_fix_then_rerun_turns_pipeline_green`) and a
negative control proving an unfixed branch still fails.

## 🚢 Deploy to Cloud Run

Build and push the image with Cloud Build, then deploy:

```bash
gcloud builds submit --config=cloudbuild.yaml --project=<PROJECT_ID> .

gcloud run deploy copa-agent \
  --image us-central1-docker.pkg.dev/<PROJECT_ID>/copa-agent-repo/copa-agent:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account <SERVICE_ACCOUNT_EMAIL> \
  --project <PROJECT_ID> \
  --set-env-vars="..."
```

(`scripts/deploy_cloud_run.sh` is an alternative single-command path if the
`gcloud` CLI source-deploy buildpack is preferred.)

## 🎥 Demo

See [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) for the 90-second walkthrough.

## 📄 License

MIT — see [`LICENSE`](LICENSE).
