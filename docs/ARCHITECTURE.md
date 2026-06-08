# Copa Agent — Architecture

Copa Agent uses a modern AI agent architecture leveraging Google Cloud and the Model Context Protocol (MCP).

## System Components

1. **Google Cloud Agent Builder (Vertex AI)**
   - Serves as the cognitive engine for the agent.
   - Handles multi-turn conversations and reasoning.
   - Configured with strict prompts to be an action-oriented DevOps commander.
   - Grounded with Vertex AI Search datastores containing World Cup runbooks.

2. **GitLab MCP Server**
   - The official `@modelcontextprotocol/server-gitlab` provides the interface between the LLM and the GitLab API.
   - Allows the agent to list pipelines, read logs, create branches, and open Merge Requests.

3. **Cloud Run Backend**
   - A Python FastAPI application that serves the frontend dashboard.
   - Proxies chat requests to Agent Builder via the `discoveryengine_v1` SDK.
   - Maintains an in-memory or Firestore-backed conversation history.
   - Handles fallback demo logic if Agent Builder is disconnected.

4. **Web Dashboard**
   - A static frontend (HTML/CSS/JS) styled for the "FIFA World Cup" theme.
   - Communicates with the Cloud Run backend via REST.
   - Displays real-time pipeline status, agent action feeds, and venue deployment maps.

## Workflow Execution

When a user asks Copa Agent to investigate a pipeline:
1. The dashboard sends the message to the Cloud Run backend.
2. The backend sends the query to the Agent Builder session.
3. The LLM determines it needs pipeline information and requests a tool call for `list_pipelines`.
4. Agent Builder executes the MCP tool call against the GitLab MCP Server.
5. The result is returned to the LLM, which reasons about the next step (e.g., calling `get_pipeline_job_log`).
6. The final response, along with the sequence of actions taken, is sent back to the dashboard.
