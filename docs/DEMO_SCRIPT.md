# 🎥 Copa Agent Demo Script (3 Minutes)

## Setup (Before Recording)
1. Open the Copa Agent dashboard at `http://localhost:8080`
2. Ensure the backend is running
3. Clear any previous chat history
4. Have the GitLab repos visible in another tab (optional)

---

## Intro (0:00 – 0:30)

**Show**: Dashboard overview

**Script**: 
> "This is Copa Agent — an AI DevOps command center for the 2026 FIFA World Cup. 
> Unlike a typical chatbot, Copa Agent doesn't just answer questions — it takes real action
> in your GitLab repositories using the GitLab MCP server.
> 
> You can see we have three World Cup microservices here — a fan app, a ticketing API, 
> and a stadium dashboard. Notice the ticketing API pipeline is failing. Let's fix that."

---

## Scenario 1: Pipeline Triage & Auto-Fix (0:30 – 1:30)

**Action**: Click on the red pipeline card OR type the message

**Type**: "The ticketing API pipeline is failing. Can you investigate?"

**Show**: 
- Action feed lighting up with tool calls in real-time
- Agent reading pipeline logs, finding the failing test
- Root cause diagnosis: TOKEN_EXPIRY_SECONDS typo (360 vs 3600)

**Script**:
> "Watch the action feed — Copa Agent is calling GitLab MCP tools in sequence.
> It listed the pipelines, found the failing job, read the job log, and diagnosed 
> the root cause: a typo in the auth token expiry constant.
> 
> Now let's have it fix the issue automatically."

**Type**: "Yes, fix it"

**Show**:
- Agent creating branch, pushing fix, opening merge request
- Actions appearing in the timeline

**Script**:
> "Copa Agent just created a fix branch, corrected the code, and opened a merge request —
> all through GitLab's MCP server. No manual work needed."

---

## Scenario 2: Smart Deployment (1:30 – 2:15)

**Type**: "Deploy all services for MetLife Stadium — there's a match tonight"

**Show**:
- Agent checking all pipelines
- Following Match Day Protocol
- Deployment readiness table

**Script**:
> "For deployments, Copa Agent follows the Match Day Protocol from our grounded runbooks.
> It checks all pipelines, waits for green across all services, then tags releases and 
> triggers deploy pipelines in dependency order.
> 
> The stadium dashboard is still running, so it waits rather than deploying blind."

---

## Scenario 3: Issue to MR (2:15 – 2:45)

**Type**: "Create an issue for adding Spanish language support to the fan app, then start working on it"

**Show**:
- Agent creating issue, branch, files, and MR in rapid succession
- 5 tool calls in the action feed

**Script**:
> "Copa Agent converts requirements into working code. It created an issue, a feature branch,
> the translation files, and a merge request — all linked together. 
> Five GitLab MCP tool calls, zero manual work."

---

## Closing (2:45 – 3:00)

**Show**: Full dashboard with all actions in the timeline

**Script**:
> "Copa Agent is built with Gemini on Google Cloud Agent Builder, integrated with 
> GitLab's MCP server for real DevOps actions. It reasons, plans, and executes — 
> keeping you in control while getting the job done.
> 
> World Cup 2026 is ready for kickoff. ⚽"

---

## Key Points to Hit
- [x] Agent takes ACTION, not just answers
- [x] Multi-step workflow (diagnose → fix → MR)
- [x] GitLab MCP integration is MEANINGFUL (5+ tool calls per scenario)
- [x] Google Cloud Agent Builder + Gemini powers the reasoning
- [x] Real-world problem: DevOps for World Cup infrastructure
- [x] User stays in control (confirms before destructive actions)
