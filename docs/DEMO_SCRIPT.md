# 🎥 Copa Agent — Demo Script (90 seconds)

A tight, judge-ready walkthrough. Everything below works in **simulation mode**
with no credentials — and identically when live creds are present.

## Setup (before recording)
1. `cd backend && python -m uvicorn main:app --port 8137`
2. Open **http://localhost:8137**, clear chat.
3. Note the **engine badge** in the top-right nav (e.g. *"● Demo Engine · GitLab sim"* →
   *"● Vertex AI · GitLab LIVE"* when credentials are set). Point this out — it shows
   the same code runs locally and in production.

---

### 0:00 – 0:15 — The problem
**Show:** the dashboard. Pipeline health is low; `worldcup-ticketing-api` is red.

> "This is Copa Agent — an *autonomous* DevOps commander for the 2026 World Cup
> platform. Three microservices, and the ticketing API's pipeline is failing. Most
> AI tools would explain the bug. Copa Agent fixes it."

### 0:15 – 1:00 — Triage → fix → MR (the money shot)
**Type** (or click *Triage Failures*):
> "The ticketing API pipeline is failing — investigate and fix it."

**Show:** the action feed streaming live, one tool at a time:
`list_pipelines → list_pipeline_jobs → get_pipeline_job_log → search_runbooks →
get_file_contents → create_branch → create_or_update_file → create_merge_request →
run_pipeline`.

> "Watch it work, live. It found pipeline #42, read the failing job log, and
> diagnosed the root cause — `TOKEN_EXPIRY_SECONDS` was 360 instead of 3600, a
> missing-zero typo that locks fans out at the gates. It **grounded the fix in our
> own runbook**, then committed the corrected file to a `fix/` branch, opened
> **MR !18**, and re-ran the pipeline — now **green**. Zero manual work."

**Highlight:** the *"📖 Playbook followed"* citation in the reply, and the MR link.

### 1:00 – 1:20 — Match Day deploy guardrails
**Type:**
> "Deploy all services for MetLife Stadium — there's a match tonight."

**Show:** the agent checks every repo and **holds** the deploy with named blockers.

> "Per the Match Day Protocol, it verifies *every* service is green before
> deploying — and refuses to deploy half-green on match day. Safety, not just speed."

### 1:20 – 1:30 — The autonomous angle + close
> "And it's not just chat — a GitLab webhook on a failed pipeline triggers this exact
> fix automatically, with no human in the loop. Built on Google Cloud Vertex AI and
> the GitLab MCP server. World Cup 2026 is ready for kickoff. ⚽"

---

## Key points to land
- [x] Agent **takes real action** (9 tool calls), not just answers
- [x] Multi-step loop: diagnose → **ground & cite** → fix → MR → **verify green**
- [x] Meaningful GitLab MCP integration (branches, commits, MRs, pipeline runs)
- [x] Google Cloud Vertex AI / Gemini powers the reasoning
- [x] Real-world stakes: fans locked out at venue gates
- [x] Autonomous webhook triage + Match Day safety guardrails
- [x] Bulletproof: dual-mode design, 12 passing tests, live engine badge
