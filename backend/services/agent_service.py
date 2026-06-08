"""
Copa Agent — Agent Builder Service
Integrates with Google Cloud Agent Builder (Vertex AI Conversation)
to send messages to the Copa Agent and receive responses with tool actions.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger("copa-agent.services.agent")

# Try to import Google Cloud SDK
try:
    from google.cloud import discoveryengine_v1 as discoveryengine
    from google.api_core.client_options import ClientOptions
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False
    logger.warning("Google Cloud Discovery Engine SDK not available. Using Gemini fallback.")

# Fallback: Try Gemini API directly
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class AgentService:
    """
    Service that communicates with the Copa Agent via Agent Builder or Gemini API.
    Supports two modes:
    1. Agent Builder (production) — uses Discovery Engine SDK
    2. Gemini API (development) — uses google-generativeai SDK as fallback
    """
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.agent_id = os.getenv("AGENT_BUILDER_AGENT_ID", "")
        self.api_key = os.getenv("GOOGLE_API_KEY", "")
        
        self.mode = "none"
        self.client = None
        self.genai_model = None
        self.sessions = {}
        
        # Try Agent Builder first
        if GCP_AVAILABLE and self.project_id and self.agent_id:
            try:
                client_options = ClientOptions(
                    api_endpoint=f"{self.location}-discoveryengine.googleapis.com"
                )
                self.client = discoveryengine.ConversationalSearchServiceClient(
                    client_options=client_options
                )
                self.mode = "agent_builder"
                logger.info(f"Agent Builder mode initialized — project: {self.project_id}, agent: {self.agent_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize Agent Builder: {e}")
        
        # Fallback to Gemini API
        if self.mode == "none" and GENAI_AVAILABLE and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.genai_model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash",
                    system_instruction=self._get_system_prompt()
                )
                self.mode = "gemini"
                logger.info("Gemini API fallback mode initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini API: {e}")
        
        if self.mode == "none":
            logger.warning("No AI backend available. Agent will return mock responses.")
            self.mode = "mock"
    
    def _get_system_prompt(self) -> str:
        """Load the system prompt from file."""
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "prompts", "system_prompt.md")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return (
                "You are Copa Agent ⚽, an AI DevOps commander for FIFA World Cup 2026. "
                "You help teams manage CI/CD pipelines, triage failures, create merge requests, "
                "and orchestrate deployments across GitLab repositories. "
                "Always prefer action over explanation."
            )
    
    async def send_message(
        self,
        message: str,
        session_id: str,
        history: Optional[List] = None
    ) -> dict:
        """
        Send a message to the agent and return the response with actions taken.
        
        Returns:
            dict with keys: reply, actions, timestamp
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        if self.mode == "agent_builder":
            return await self._send_agent_builder(message, session_id, timestamp)
        elif self.mode == "gemini":
            return await self._send_gemini(message, session_id, history, timestamp)
        else:
            return self._mock_response(message, timestamp)
    
    async def _send_agent_builder(self, message: str, session_id: str, timestamp: str) -> dict:
        """Send message via Agent Builder Discovery Engine."""
        try:
            # Build the session name
            session_name = (
                f"projects/{self.project_id}/locations/{self.location}"
                f"/collections/default_collection/engines/{self.agent_id}"
                f"/sessions/{session_id}"
            )
            
            query = discoveryengine.TextInput(input=message)
            request = discoveryengine.ConverseConversationRequest(
                name=session_name,
                query=query,
            )
            
            response = self.client.converse_conversation(request=request)
            
            reply_text = response.reply.text if response.reply else "I couldn't process that request."
            
            # Extract actions from tool calls if available
            actions = []
            if hasattr(response, 'search_results'):
                for result in response.search_results:
                    actions.append({
                        "tool": "search",
                        "description": f"Retrieved: {result.document.name}",
                        "status": "completed",
                        "result": str(result)[:200]
                    })
            
            return {"reply": reply_text, "actions": actions, "timestamp": timestamp}
            
        except Exception as e:
            logger.error(f"Agent Builder error: {e}")
            return {
                "reply": f"Error communicating with Agent Builder: {e}",
                "actions": [],
                "timestamp": timestamp
            }
    
    async def _send_gemini(
        self, message: str, session_id: str,
        history: Optional[List], timestamp: str
    ) -> dict:
        """Send message via Gemini API with conversation history."""
        try:
            # Get or create chat session
            if session_id not in self.sessions:
                self.sessions[session_id] = self.genai_model.start_chat(history=[])
            
            chat = self.sessions[session_id]
            response = chat.send_message(message)
            
            reply_text = response.text
            
            # Parse actions from response (agent describes them in text)
            actions = self._extract_actions_from_text(reply_text)
            
            return {"reply": reply_text, "actions": actions, "timestamp": timestamp}
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {
                "reply": f"Error communicating with Gemini: {e}",
                "actions": [],
                "timestamp": timestamp
            }
    
    def _mock_response(self, message: str, timestamp: str) -> dict:
        """Return a mock response for development without API keys."""
        msg_lower = message.lower()
        
        if "pipeline" in msg_lower and ("fail" in msg_lower or "broken" in msg_lower):
            return {
                "reply": (
                    "⚡ Investigating the failing pipeline...\n\n"
                    "I found Pipeline #42 in `worldcup-ticketing-api` has status **failed**.\n\n"
                    "**Root Cause**: The `unit_test` job failed. The test `test_auth_token_validation` "
                    "in `tests/test_auth.py` is failing because `TOKEN_EXPIRY_SECONDS` was changed "
                    "from `3600` to `360` — likely a typo (missing a zero).\n\n"
                    "Want me to create a fix branch and merge request to correct this? ⚽"
                ),
                "actions": [
                    {"tool": "list_pipelines", "description": "Listed pipelines for worldcup-ticketing-api", "status": "completed", "result": "Pipeline #42 — FAILED"},
                    {"tool": "list_pipeline_jobs", "description": "Listed jobs for pipeline #42", "status": "completed", "result": "Job 'unit_test' — FAILED"},
                    {"tool": "get_pipeline_job_log", "description": "Read job log for failing test", "status": "completed", "result": "AssertionError: Expected 3600, got 360"},
                ],
                "timestamp": timestamp
            }
        
        elif "deploy" in msg_lower:
            return {
                "reply": (
                    "⚡ Checking deployment readiness across all World Cup services...\n\n"
                    "| Service | Pipeline | Status |\n"
                    "|---------|----------|--------|\n"
                    "| worldcup-fan-app | #78 | ✅ Passed |\n"
                    "| worldcup-ticketing-api | #43 | ✅ Passed |\n"
                    "| worldcup-stadium-dashboard | #31 | 🔄 Running |\n\n"
                    "Stadium dashboard pipeline is still running. I'll deploy once all services are green. "
                    "Following Match Day Protocol. ⚽"
                ),
                "actions": [
                    {"tool": "list_pipelines", "description": "Checked fan-app pipelines", "status": "completed", "result": "Pipeline #78 — PASSED"},
                    {"tool": "list_pipelines", "description": "Checked ticketing-api pipelines", "status": "completed", "result": "Pipeline #43 — PASSED"},
                    {"tool": "list_pipelines", "description": "Checked stadium-dashboard pipelines", "status": "completed", "result": "Pipeline #31 — RUNNING"},
                ],
                "timestamp": timestamp
            }
        
        elif "status" in msg_lower or "overview" in msg_lower:
            return {
                "reply": (
                    "⚽ **World Cup 2026 Platform Status Report**\n\n"
                    "| Service | Latest Pipeline | Status | Branch |\n"
                    "|---------|----------------|--------|--------|\n"
                    "| worldcup-fan-app | #78 | ✅ Passed | main |\n"
                    "| worldcup-ticketing-api | #42 | ❌ Failed | main |\n"
                    "| worldcup-stadium-dashboard | #31 | 🔄 Running | main |\n\n"
                    "**Summary**: 1 healthy, 1 failing, 1 in progress.\n"
                    "The ticketing-api failure is a unit test issue in auth token validation. "
                    "Want me to triage and fix it?"
                ),
                "actions": [
                    {"tool": "list_pipelines", "description": "Aggregated status across all repos", "status": "completed", "result": "3 projects checked"},
                ],
                "timestamp": timestamp
            }
        
        elif "issue" in msg_lower or "create" in msg_lower:
            return {
                "reply": (
                    "⚡ Creating the issue and starting implementation...\n\n"
                    "✅ **Issue #23** created: \"feat: Add Spanish (es) language support\"\n"
                    "✅ **Branch** created: `feature/spanish-i18n`\n"
                    "✅ **MR #18** opened: \"feat: Add Spanish language support\" → linked to Issue #23\n\n"
                    "The MR includes initial i18n config and translation files. Your team can review "
                    "and add any missing translations. ¡Vamos! ⚽"
                ),
                "actions": [
                    {"tool": "create_issue", "description": "Created issue #23 for Spanish i18n", "status": "completed", "result": "Issue #23 created"},
                    {"tool": "create_branch", "description": "Created branch feature/spanish-i18n", "status": "completed", "result": "Branch created from main"},
                    {"tool": "create_or_update_file", "description": "Created es.json translation file", "status": "completed", "result": "File created"},
                    {"tool": "create_merge_request", "description": "Opened MR #18", "status": "completed", "result": "MR #18 opened"},
                ],
                "timestamp": timestamp
            }
        
        else:
            return {
                "reply": (
                    f"⚽ Copa Agent here! I'm your AI DevOps commander for World Cup 2026.\n\n"
                    f"I can help you with:\n"
                    f"- 🔍 **Triage pipeline failures** — \"The ticketing API pipeline is failing\"\n"
                    f"- 🚀 **Deploy services** — \"Deploy all services for MetLife Stadium\"\n"
                    f"- 📊 **Platform status** — \"What's the status of all our pipelines?\"\n"
                    f"- 📝 **Create issues & MRs** — \"Create an issue for Spanish language support\"\n"
                    f"- 🔄 **Manage merge requests** — \"List open MRs in the fan app\"\n\n"
                    f"What would you like me to do?"
                ),
                "actions": [],
                "timestamp": timestamp
            }
    
    def _extract_actions_from_text(self, text: str) -> list:
        """Extract action indicators from agent response text."""
        actions = []
        lines = text.split("\n")
        for line in lines:
            if line.strip().startswith("⚡"):
                actions.append({
                    "tool": "gitlab_action",
                    "description": line.strip().replace("⚡", "").strip(),
                    "status": "completed",
                    "result": None
                })
        return actions
