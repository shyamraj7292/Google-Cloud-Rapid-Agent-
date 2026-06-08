# ⚽ Copa Agent: AI DevOps Commander for World Cup 2026

**Built for the "Building Agents for Real-World Challenges" Hackathon (GitLab Track)**

Copa Agent is a multi-step, action-oriented AI agent that serves as an intelligent DevOps co-pilot for teams building the massive infrastructure required for the 2026 FIFA World Cup.

Powered by **Google Cloud Agent Builder** and connected to the **GitLab Model Context Protocol (MCP)** server, Copa Agent doesn't just chat—it takes autonomous action to triage failing pipelines, fix code, and orchestrate complex deployments across multiple microservices.

## 🌟 Key Features

- **Pipeline Triage & Auto-Fix**: The agent reads GitLab CI logs, diagnoses failures, creates fix branches, and opens Merge Requests natively.
- **Smart Deployment Orchestrator**: Understands "Match Day Protocols", verifies all dependent pipelines are green, creates tags, and triggers multi-repo deployments.
- **Issue-to-MR Automation**: Converts issue requests directly into code and draft Merge Requests.
- **Premium Command Center**: A sleek, dark-mode dashboard showing cross-repo pipeline health, an agent activity timeline, and venue deployment status.

## 🏗️ Architecture

- **Agent Engine**: Google Cloud Agent Builder (Gemini 2.5)
- **Integration**: GitLab MCP Server (`@modelcontextprotocol/server-gitlab`)
- **Backend**: Python FastAPI (deployed on Cloud Run)
- **Frontend**: HTML/CSS/JS (served by FastAPI)
- **Grounding**: Vertex AI Search Datastore (World Cup Runbooks)

See `docs/ARCHITECTURE.md` for a detailed diagram.

## 🚀 Setup Instructions

### 1. Prerequisites
- A Google Cloud Project with the Discovery Engine API enabled.
- A GitLab Personal Access Token (`api`, `read_repository`, `write_repository` scopes).
- Python 3.10+ and Node.js (for `npx`).

### 2. Local Development
```bash
# Clone the repo
git clone https://github.com/your-username/Google-Cloud-Rapid-Agent.git
cd Google-Cloud-Rapid-Agent

# Setup Python backend
cd backend
python -m venv venv
source venv/bin/activate  # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt

# Configure environment
cp ../.env.example ../.env
# Edit ../.env with your GCP details and GitLab Token

# Run the server
uvicorn main:app --reload --port 8080
```
Visit `http://localhost:8080` to access the Copa Agent dashboard.

### 3. Deploy to Cloud Run
Use the included script to deploy the agent:
```bash
bash scripts/deploy_cloud_run.sh
```

## 🎥 Demo

Check out our 3-minute demo video showing the agent auto-fixing a pipeline failure and orchestrating a Match Day deployment! (Link provided in Devpost).

## 📄 License

MIT License. See `LICENSE` for more information.