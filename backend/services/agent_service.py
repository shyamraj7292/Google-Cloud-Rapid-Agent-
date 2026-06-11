"""
Copa Agent — Agentic Service (real tool-calling loop)
=====================================================

This is the brain. Unlike a chatbot, Copa Agent runs a *reason → act → observe*
loop: it decides which GitLab tool to call, the tool actually runs (via
GitLabToolExecutor), the result is fed back, and it keeps going until the job is
done. Every step is surfaced to the UI as it happens.

Three execution backends, chosen automatically:

  1. "gemini"   — google-genai (new SDK) with native function calling. The model
                  drives the loop; we execute each requested tool and return the
                  result until it stops calling tools.

  2. "vertex"   — Vertex AI (google-cloud-aiplatform) function calling, used when
                  a full GCP project is configured. Same loop, enterprise path.

  3. "scripted" — no LLM available. A deterministic planner that still executes
                  the *real* tool calls end-to-end (triage → fix → MR → re-run),
                  so the headline demo always works. This is what guarantees the
                  agent never "dies on stage".

All three yield the identical event stream, so routes/UI are backend-agnostic.
"""

import os
import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator

from services.gitlab_tools import GitLabToolExecutor
from services.grounding_service import GroundingService

logger = logging.getLogger("copa-agent.services.agent")

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    import vertexai
    from vertexai.generative_models import (
        GenerativeModel as Vx_Model, Tool as Vx_Tool,
        FunctionDeclaration as Vx_FuncDecl, Part as Vx_Part,
    )
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------------
#  TOOL SCHEMAS  (the contract the model plans against)
# ----------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "name": "list_pipelines",
        "description": "List recent CI/CD pipelines for a World Cup project to find failing or running ones.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string", "description": "Project name, e.g. 'worldcup-ticketing-api'."},
            "limit": {"type": "integer", "description": "Max pipelines to return."},
        }, "required": ["project"]},
    },
    {
        "name": "list_pipeline_jobs",
        "description": "List the jobs in a pipeline to identify which job failed.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "pipeline_id": {"type": "integer"},
        }, "required": ["project", "pipeline_id"]},
    },
    {
        "name": "get_pipeline_job_log",
        "description": "Read the log output of a job to diagnose the root cause of a failure.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "job_name": {"type": "string"},
            "pipeline_id": {"type": "integer"},
        }, "required": ["project", "job_name"]},
    },
    {
        "name": "get_file_contents",
        "description": "Read a source file from a repo so you can prepare a precise fix.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "file_path": {"type": "string"},
            "ref": {"type": "string"},
        }, "required": ["project", "file_path"]},
    },
    {
        "name": "create_branch",
        "description": "Create a new branch (typically a fix/ branch) from the default branch.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "branch": {"type": "string"},
            "ref": {"type": "string"},
        }, "required": ["project", "branch"]},
    },
    {
        "name": "create_or_update_file",
        "description": "Commit a file change to a branch. Use this to apply the actual code fix.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "file_path": {"type": "string"},
            "content": {"type": "string", "description": "Full new file content."},
            "branch": {"type": "string"},
            "commit_message": {"type": "string"},
        }, "required": ["project", "file_path", "content", "branch", "commit_message"]},
    },
    {
        "name": "create_merge_request",
        "description": "Open a merge request from a source branch into the target branch.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "source_branch": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "target_branch": {"type": "string"},
        }, "required": ["project", "source_branch", "title"]},
    },
    {
        "name": "create_issue",
        "description": "Create a GitLab issue to track a feature request or bug.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
        }, "required": ["project", "title"]},
    },
    {
        "name": "run_pipeline",
        "description": "Trigger a pipeline on a branch to verify a fix actually passes.",
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "ref": {"type": "string"},
        }, "required": ["project", "ref"]},
    },
    {
        "name": "get_platform_status",
        "description": "Get the latest pipeline status across ALL World Cup repos (health overview / deploy-readiness).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "search_runbooks",
        "description": ("Search the team's World Cup runbooks and CI/CD playbooks for the relevant "
                        "procedure BEFORE acting. Always ground your fix in a cited playbook section."),
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What you need guidance on, e.g. 'unit test AssertionError fix'."},
        }, "required": ["query"]},
    },
    {
        "name": "write_runbook_entry",
        "description": ("Document a NEW fix pattern back into the team's runbooks so future incidents "
                        "of this type are covered. Use this AFTER a fix when search_runbooks did not "
                        "return a good citation for the issue you just resolved — this is how the "
                        "agent gets smarter over time."),
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string", "description": "Short heading for the new playbook section, e.g. 'Token Expiry Misconfiguration'."},
            "content": {"type": "string", "description": "Markdown body: symptom, root cause, fix steps, and prevention."},
            "source": {"type": "string", "description": "Which playbook file to append to (without extension). Defaults to 'pipeline_playbooks'."},
        }, "required": ["title", "content"]},
    },
    {
        "name": "get_stadium_traffic",
        "description": ("Match Day Simulator: check real, live CI/CD pipeline activity across all "
                        "World Cup repos in the last 15 minutes as a load proxy for a stadium's "
                        "services. A burst of recent pipeline runs is treated as a surge. Use this "
                        "to detect demand spikes around kickoff."),
        "parameters": {"type": "object", "properties": {
            "stadium": {"type": "string", "description": "Stadium name, e.g. 'MetLife Stadium'."},
        }, "required": ["stadium"]},
    },
    {
        "name": "scale_service",
        "description": ("Scale a service's replica count to handle increased load. Use this when "
                        "get_stadium_traffic reports a surge that puts a service at risk."),
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "replicas": {"type": "integer", "description": "New replica/instance count."},
        }, "required": ["project", "replicas"]},
    },
    {
        "name": "create_postmortem",
        "description": ("Publish a structured incident postmortem (timeline, root cause, fix, "
                        "prevention) as a GitLab wiki page. Use this AFTER an autonomous fix has "
                        "been applied and verified."),
        "parameters": {"type": "object", "properties": {
            "project": {"type": "string"},
            "title": {"type": "string", "description": "Postmortem title, e.g. 'Postmortem: Ticketing API Auth Token Expiry'."},
            "content": {"type": "string", "description": "Full markdown postmortem with ## Timeline, ## Root Cause, ## Fix, ## Prevention sections."},
        }, "required": ["project", "title", "content"]},
    },
]

# Tools that pause for human approval before executing — risky/irreversible
# actions. The dashboard must explicitly approve or reject before they run.
GATED_TOOLS = {"create_merge_request", "run_pipeline", "scale_service"}


class AgentService:
    MAX_STEPS = 10

    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.api_key = os.getenv("GOOGLE_API_KEY", "")
        self.model_name = os.getenv("COPA_MODEL", "gemini-2.5-flash")
        self.tools = GitLabToolExecutor()
        self.grounding = GroundingService()

        self.mode = "scripted"
        self.genai_model = None
        self.vertex_model = None

        # Human-in-the-loop approval gates for risky tools (create_merge_request,
        # run_pipeline). Keyed by approval_id.
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_decisions: dict[str, bool] = {}

        # Prefer Vertex (full GCP) → Gemini API key → scripted.
        if VERTEX_AVAILABLE and self.project_id and not self.project_id.startswith("your-") and not self.api_key:
            try:
                vertexai.init(project=self.project_id, location=self.location)
                vx_tool = Vx_Tool(function_declarations=[
                    Vx_FuncDecl(name=t["name"], description=t["description"],
                                parameters=t["parameters"]) for t in TOOL_SCHEMAS
                ])
                self.vertex_model = Vx_Model(
                    self.model_name,
                    system_instruction=self._system_prompt(),
                    tools=[vx_tool],
                )
                self.mode = "vertex"
                logger.info(f"Agent backend: VERTEX ({self.model_name}, project {self.project_id}).")
            except Exception as e:
                logger.warning(f"Vertex init failed: {e}")

        if self.mode == "scripted" and GENAI_AVAILABLE and self.api_key and not self.api_key.startswith("your-"):
            try:
                self.genai_client = genai.Client(api_key=self.api_key)
                self._genai_tool = genai_types.Tool(function_declarations=TOOL_SCHEMAS)
                self._genai_config = genai_types.GenerateContentConfig(
                    system_instruction=self._system_prompt(),
                    tools=[self._genai_tool],
                )
                self.mode = "gemini"
                logger.info(f"Agent backend: GEMINI/{self.model_name} (google-genai SDK).")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

        if self.mode == "scripted":
            logger.info("Agent backend: SCRIPTED (deterministic planner, real tool calls).")

        logger.info(f"GitLab tools running in '{self.tools.mode}' mode.")

    # -- prompt --------------------------------------------------------------
    def _system_prompt(self) -> str:
        path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "agent", "prompts", "system_prompt.md")
        try:
            with open(path, "r", encoding="utf-8") as f:
                base = f.read()
        except FileNotFoundError:
            base = "You are Copa Agent, an AI DevOps commander for FIFA World Cup 2026."
        return base + (
            "\n\n## Execution Contract\n"
            "You operate as an autonomous agent with a reason→act→observe loop. "
            "When the user reports a problem, DO NOT just describe a fix — investigate "
            "with your tools, then APPLY the fix: read the failing job log, read the "
            "offending file, create a `fix/...` branch, commit the corrected file, open "
            "a merge request, and run the pipeline on the branch to prove it passes. "
            "Reference project names without the group prefix (e.g. 'worldcup-ticketing-api'). "
            "When you have completed the work, give a concise final summary with the MR link.\n\n"
            "## Self-Improving Runbooks\n"
            "If `search_runbooks` returns no good citation for the issue you're fixing, call "
            "`write_runbook_entry` AFTER the fix is verified to document the symptom, root cause, "
            "fix steps, and prevention — so the same issue is grounded next time.\n\n"
            "## Postmortems\n"
            "After an autonomous fix has been applied and the pipeline re-run, call "
            "`create_postmortem` to publish a structured wiki page with ## Timeline, ## Root Cause, "
            "## Fix, and ## Prevention sections, and link to it in your final summary.\n\n"
            "## Human Approval\n"
            "`create_merge_request`, `run_pipeline`, and `scale_service` require operator approval — "
            "when you call them, execution will pause until a human approves or rejects in the "
            "dashboard. If rejected, acknowledge it and stop rather than retrying the same action.\n\n"
            "## Match Day Simulator\n"
            "When asked about a traffic surge, crowd, kickoff, or stadium load, call "
            "`get_stadium_traffic` to check live CI/CD pipeline activity as a load proxy. If it "
            "reports a surge, check `get_platform_status` for the affected service's health, then "
            "propose and call `scale_service` (commits an updated replica count to the project's "
            "k8s/deployment.yaml). Tie your narration to the World Cup match-day stakes, but report "
            "only the real numbers returned by the tools."
        )

    # -- tool dispatch -------------------------------------------------------
    async def _execute_tool(self, name: str, args: dict) -> dict:
        if name == "search_runbooks":
            return self.grounding.search(args.get("query", ""))
        if name == "write_runbook_entry":
            return self.grounding.write_entry(
                args.get("source", "pipeline_playbooks"),
                args.get("title", "Untitled"),
                args.get("content", ""),
            )
        if name == "create_postmortem":
            return await self.tools.create_wiki_page(
                args.get("project", ""), args.get("title", "Postmortem"), args.get("content", ""))
        fn = getattr(self.tools, name, None)
        if not fn:
            return {"ok": False, "error": f"Unknown tool '{name}'"}
        try:
            # The 5 write/read ops (get_file_contents, create_branch,
            # create_or_update_file, create_merge_request, create_issue) are
            # now async to support the MCP path — await them; everything else
            # (list_pipelines, run_pipeline, …) stays synchronous.
            if asyncio.iscoroutinefunction(fn):
                return await fn(**args)
            return fn(**args)
        except TypeError as e:
            return {"ok": False, "error": f"Bad arguments for {name}: {e}"}
        except Exception as e:
            logger.error(f"Tool {name} raised: {e}")
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _humanize(name: str, args: dict, result: dict) -> str:
        """Short human-readable description of an executed tool call for the UI."""
        if name == "list_pipelines":
            pls = result.get("pipelines", [])
            bad = next((p for p in pls if p.get("status") == "failed"), None)
            if bad:
                return f"Listed pipelines for {args.get('project')} — found #{bad['id']} FAILED"
            return f"Listed {len(pls)} pipelines for {args.get('project')}"
        if name == "list_pipeline_jobs":
            jobs = result.get("jobs", [])
            failed = [j["name"] for j in jobs if j.get("status") == "failed"]
            return f"Inspected jobs in pipeline #{args.get('pipeline_id')} — failing: {', '.join(failed) or 'none'}"
        if name == "get_pipeline_job_log":
            return f"Read job log for '{args.get('job_name')}' — diagnosed root cause"
        if name == "get_file_contents":
            return f"Read {args.get('file_path')} from {args.get('project')}"
        if name == "create_branch":
            return f"Created branch '{args.get('branch')}' in {args.get('project')}"
        if name == "create_or_update_file":
            return f"Committed fix to {args.get('file_path')} on '{args.get('branch')}'"
        if name == "create_merge_request":
            return f"Opened MR !{result.get('mr_iid')} — {args.get('title')}"
        if name == "create_issue":
            return f"Created issue #{result.get('issue_iid')} — {args.get('title')}"
        if name == "run_pipeline":
            return f"Ran pipeline on '{args.get('ref')}' — status: {result.get('status', '?').upper()}"
        if name == "get_platform_status":
            return "Aggregated pipeline health across all World Cup repos"
        if name == "search_runbooks":
            cits = result.get("citations", [])
            top = cits[0] if cits else None
            return (f"Grounded in runbook: {top['source']} › {top['section']}"
                    if top else "Searched runbooks (no match)")
        if name == "write_runbook_entry":
            return f"📖 Documented new playbook entry: '{args.get('title')}' → {result.get('source')}.md"
        if name == "create_postmortem":
            return f"📄 Published postmortem wiki page: '{args.get('title')}'"
        if name == "get_stadium_traffic":
            if result.get("surge"):
                return (f"⚡ Surge signal at {args.get('stadium')}: "
                        f"{result.get('recent_pipeline_runs')} pipeline runs in the last "
                        f"{result.get('window_minutes')} min")
            return (f"Checked platform load for {args.get('stadium')} — "
                    f"{result.get('recent_pipeline_runs', 0)} pipeline runs in the last "
                    f"{result.get('window_minutes', 15)} min, no surge")
        if name == "scale_service":
            return (f"Scaled {args.get('project')} to {result.get('replicas')} replicas "
                    f"(was {result.get('previous_replicas')})")
        return f"Executed {name}"

    @staticmethod
    def _humanize_pending(name: str, args: dict) -> str:
        """Description of a tool call awaiting human approval, before it runs."""
        if name == "create_merge_request":
            return (f"Open a merge request on '{args.get('project')}': "
                    f"{args.get('source_branch')} → {args.get('target_branch', 'main')} "
                    f"— \"{args.get('title')}\"")
        if name == "run_pipeline":
            return f"Run the CI/CD pipeline on '{args.get('project')}' branch '{args.get('ref')}'"
        if name == "scale_service":
            return f"Scale '{args.get('project')}' to {args.get('replicas')} replicas"
        return f"Execute {name}"

    # -- human-in-the-loop approval gate -------------------------------------
    def resolve_approval(self, approval_id: str, approved: bool) -> bool:
        event = self._pending_approvals.get(approval_id)
        if not event:
            return False
        self._approval_decisions[approval_id] = approved
        event.set()
        return True

    async def _gated_execute(self, name: str, args: dict, session_id: str):
        """Execute a tool, optionally pausing for human approval first.

        Yields ("event", event_dict) for each event to surface to the UI, and
        finally ("result", result_dict) with the tool's result.
        """
        if name in GATED_TOOLS:
            approval_id = str(uuid.uuid4())
            description = self._humanize_pending(name, args)
            event = asyncio.Event()
            self._pending_approvals[approval_id] = event
            yield ("event", {
                "type": "approval_request", "approval_id": approval_id, "tool": name,
                "args": args, "description": description, "session_id": session_id,
                "timestamp": _now(),
            })
            try:
                await asyncio.wait_for(event.wait(), timeout=180)
                approved = self._approval_decisions.pop(approval_id, False)
            except asyncio.TimeoutError:
                approved = False
            finally:
                self._pending_approvals.pop(approval_id, None)
            if not approved:
                result = {"ok": False, "error": "Action rejected by operator — not executed.",
                          "approval": "rejected"}
                yield ("event", {
                    "type": "action", "tool": name,
                    "description": f"⛔ Rejected by operator: {description}",
                    "status": "rejected", "result": json.dumps(result)[:400], "timestamp": _now(),
                })
                yield ("result", result)
                return
            yield ("event", {"type": "status", "text": f"✅ Approved — executing {name}…", "timestamp": _now()})
        result = await self._execute_tool(name, args)
        yield ("event", {
            "type": "action", "tool": name,
            "description": self._humanize(name, args, result),
            "status": "completed" if result.get("ok") else "failed",
            "result": json.dumps(result)[:400], "timestamp": _now(),
        })
        yield ("result", result)

    # ========================================================================
    #  PUBLIC: streaming agent run
    #  Yields event dicts: {type, ...}
    #    type=status   → short "thinking" line
    #    type=action   → a tool was executed {tool, description, status, result}
    #    type=reply    → final assistant message {reply}
    #    type=done
    # ========================================================================
    async def run_stream(self, message: str, session_id: str,
                         history: Optional[list] = None) -> AsyncGenerator[dict, None]:
        if self.mode == "gemini":
            async for ev in self._run_gemini(message, session_id):
                yield ev
        elif self.mode == "vertex":
            async for ev in self._run_vertex(message, session_id):
                yield ev
        else:
            async for ev in self._run_scripted(message, session_id):
                yield ev
        yield {"type": "done", "timestamp": _now()}

    # Non-streaming convenience wrapper (collects the stream).
    async def send_message(self, message: str, session_id: str,
                           history: Optional[list] = None) -> dict:
        reply, actions = "", []
        async for ev in self.run_stream(message, session_id, history):
            if ev["type"] == "action":
                actions.append({k: ev[k] for k in ("tool", "description", "status", "result")})
            elif ev["type"] == "reply":
                reply = ev["reply"]
        return {"reply": reply, "actions": actions, "timestamp": _now()}

    # -- Gemini backend (google-genai SDK) -----------------------------------
    async def _run_gemini(self, message: str, session_id: str):
        sessions = getattr(self, "_gemini_sessions", None)
        if sessions is None:
            sessions = self._gemini_sessions = {}
        if session_id not in sessions:
            sessions[session_id] = self.genai_client.chats.create(
                model=self.model_name,
                config=self._genai_config,
            )
        chat = sessions[session_id]

        try:
            response = chat.send_message(message)
            for _ in range(self.MAX_STEPS):
                calls = self._extract_genai_calls(response)
                if not calls:
                    break
                tool_responses = []
                for name, args in calls:
                    yield {"type": "status", "text": f"Calling {name}…", "timestamp": _now()}
                    result = {}
                    async for kind, payload in self._gated_execute(name, args, session_id):
                        if kind == "event":
                            yield payload
                        else:
                            result = payload
                    tool_responses.append(
                        genai_types.Part.from_function_response(
                            name=name, response={"result": result}
                        )
                    )
                response = chat.send_message(tool_responses)
            final = self._safe_text(response) or "Done. ⚽"
            yield {"type": "reply", "reply": final, "timestamp": _now()}
        except Exception as e:
            logger.error(f"Gemini loop error: {e}")
            async for ev in self._run_scripted(message, session_id):
                yield ev

    def _extract_genai_calls(self, response):
        calls = []
        try:
            for part in response.candidates[0].content.parts:
                fc = getattr(part, "function_call", None)
                if fc and fc.name:
                    calls.append((fc.name, dict(fc.args)))
        except (IndexError, AttributeError):
            pass
        return calls

    def _safe_text(self, response) -> str:
        try:
            return response.text.strip()
        except Exception:
            try:
                return "".join(
                    p.text for p in response.candidates[0].content.parts
                    if getattr(p, "text", "")
                ).strip()
            except Exception:
                return ""

    # -- Vertex backend ------------------------------------------------------
    async def _run_vertex(self, message: str, session_id: str):
        sessions = getattr(self, "_vertex_sessions", None)
        if sessions is None:
            sessions = self._vertex_sessions = {}
        if session_id not in sessions:
            sessions[session_id] = self.vertex_model.start_chat()
        chat = sessions[session_id]
        try:
            response = chat.send_message(message)
            for _ in range(self.MAX_STEPS):
                parts = response.candidates[0].content.parts
                fcs = [p.function_call for p in parts if getattr(p, "function_call", None) and p.function_call.name]
                if not fcs:
                    break
                tool_parts = []
                for fc in fcs:
                    name, args = fc.name, dict(fc.args)
                    yield {"type": "status", "text": f"Calling {name}…", "timestamp": _now()}
                    result = await self._execute_tool(name, args)
                    yield {
                        "type": "action", "tool": name,
                        "description": self._humanize(name, args, result),
                        "status": "completed" if result.get("ok") else "failed",
                        "result": json.dumps(result)[:400], "timestamp": _now(),
                    }
                    tool_parts.append(Vx_Part.from_function_response(
                        name=name, response={"result": result}))
                response = chat.send_message(tool_parts)
            final = ""
            try:
                final = response.text.strip()
            except Exception:
                pass
            yield {"type": "reply", "reply": final or "Done. ⚽", "timestamp": _now()}
        except Exception as e:
            logger.error(f"Vertex loop error: {e}")
            async for ev in self._run_scripted(message, session_id):
                yield ev

    # -- Fallback backend (no LLM available, or the LLM call failed) --------
    async def _run_scripted(self, message: str, session_id: str):
        """Used only when no AI backend is configured/available, or the gemini/
        vertex call raised. Reports real, live platform status from GitLab —
        never fabricates fixes, branches, MRs, or postmortems."""

        async def act(name, args):
            result = await self._execute_tool(name, args)
            return {
                "type": "action", "tool": name,
                "description": self._humanize(name, args, result),
                "status": "completed" if result.get("ok") else "failed",
                "result": json.dumps(result)[:400], "timestamp": _now(),
            }, result

        yield {"type": "status", "text": "AI model unavailable — fetching live platform status…", "timestamp": _now()}
        ev, status_res = await act("get_platform_status", {})
        yield ev

        if not status_res.get("ok"):
            yield {"type": "reply", "timestamp": _now(), "reply": (
                "⚠️ I couldn't reach the AI model or GitLab right now "
                f"({status_res.get('error', 'unknown error')}). Please try again shortly.")}
            return

        rows = status_res.get("projects", [])
        icon = {"success": "✅ Passed", "failed": "❌ Failed", "running": "🔄 Running",
                "pending": "⏳ Pending", "canceled": "⛔ Canceled"}
        table = "\n".join(f"| `{r['project'].split('/')[-1]}` | {icon.get(r['status'], r['status'])} |"
                          for r in rows)
        healthy = sum(1 for r in rows if r["status"] == "success")
        yield {"type": "reply", "timestamp": _now(), "reply": (
            "⚠️ **The AI reasoning model is temporarily unavailable**, so I can't plan a "
            "multi-step fix right now — but here's the live platform status:\n\n"
            f"| Service | Pipeline |\n|---|---|\n{table}\n\n"
            f"**{healthy}/{len(rows)} green.** Please retry your request in a moment.")}
