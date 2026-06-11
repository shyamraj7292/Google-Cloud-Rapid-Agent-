"""
Copa Agent — GitLab MCP Client
================================
Connects to the official GitLab MCP server (@modelcontextprotocol/server-gitlab)
via the stdio transport and exposes the tools Copa Agent needs.

This is the layer that satisfies the hackathon's "Partner Power" requirement:
meaningful MCP integration with GitLab (the partner), using the actual MCP
protocol — not just a direct API call.

Supported MCP tools (write operations — most impactful in the triage→fix→MR flow):
  • get_file_contents    — read a file from a GitLab repo
  • create_branch        — create a feature/fix branch
  • create_or_update_file — commit the actual code fix
  • create_merge_request — open the MR
  • create_issue         — file a bug/feature issue

Pipeline read operations (list_pipelines, get_pipeline_job_log, run_pipeline etc.)
are not in the official GitLab MCP server and continue to use python-gitlab via
GitLabToolExecutor — this is a hybrid MCP+API design, and we're transparent about it.
"""

import os
import json
import logging
import asyncio
from typing import Any, Optional

logger = logging.getLogger("copa-agent.services.mcp")

try:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not installed — GitLab MCP integration disabled.")

# Tools handled via MCP (write + file operations)
MCP_TOOL_NAMES = {
    "get_file_contents",
    "create_branch",
    "create_or_update_file",
    "create_merge_request",
    "create_issue",
}


class MCPGitLabClient:
    """
    Async client for the GitLab MCP server.

    Lifecycle:
      - Call await client.start() once at startup (or use as async context manager).
      - Call await client.call_tool(name, args) to invoke a GitLab MCP tool.
      - Call await client.stop() on shutdown.
    """

    def __init__(self, token: str, api_url: str, group_path: str):
        self.token = token
        self.api_url = api_url
        self.group_path = group_path
        self._session: Optional[Any] = None
        self._cm_stdio = None
        self._cm_session = None
        self.available = False

    async def start(self):
        if not MCP_AVAILABLE:
            logger.warning("MCP SDK unavailable — skipping MCP client startup.")
            return
        if not self.token or self.token.startswith("glpat-xxxx"):
            logger.info("No valid GitLab token — MCP client not started.")
            return
        try:
            params = StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-gitlab"],
                env={
                    "GITLAB_PERSONAL_ACCESS_TOKEN": self.token,
                    "GITLAB_API_URL": self.api_url,
                    "PATH": os.environ.get("PATH", ""),
                },
            )
            self._cm_stdio = stdio_client(params)
            read, write = await self._cm_stdio.__aenter__()
            self._cm_session = ClientSession(read, write)
            self._session = await self._cm_session.__aenter__()
            await self._session.initialize()
            self.available = True
            logger.info("GitLab MCP server connected via stdio (npx @modelcontextprotocol/server-gitlab).")
        except Exception as e:
            logger.warning(f"GitLab MCP server failed to start: {e} — falling back to python-gitlab.")
            self.available = False

    async def stop(self):
        try:
            if self._cm_session:
                await self._cm_session.__aexit__(None, None, None)
            if self._cm_stdio:
                await self._cm_stdio.__aexit__(None, None, None)
        except Exception:
            pass
        self.available = False
        logger.info("GitLab MCP client stopped.")

    async def call_tool(self, name: str, args: dict) -> dict:
        """
        Call a GitLab MCP tool and return a normalized {ok, ...} dict
        matching the shape GitLabToolExecutor already returns so the rest
        of the agent code needs no changes.
        """
        if not self.available or self._session is None:
            return {"ok": False, "error": "MCP client not available"}
        try:
            result = await self._session.call_tool(name, args)
            # MCP returns CallToolResult with .content list of ContentBlock
            # Each block has .type ("text"/"image") and .text
            if result.isError:
                text = " ".join(c.text for c in result.content if hasattr(c, "text"))
                return {"ok": False, "error": f"MCP tool error: {text}"}
            text = " ".join(c.text for c in result.content if hasattr(c, "text"))
            # Try to parse as JSON (most GitLab MCP responses are JSON strings)
            try:
                data = json.loads(text)
                return {"ok": True, "mcp": True, **data}
            except (json.JSONDecodeError, TypeError):
                return {"ok": True, "mcp": True, "result": text}
        except Exception as e:
            logger.error(f"MCP tool call '{name}' failed: {e}")
            return {"ok": False, "error": f"MCP call failed: {e}"}

    def _resolve_project_id(self, project: str) -> str:
        """Accept 'worldcup-ticketing-api' or full 'shyamraj10335/worldcup-ticketing-api'."""
        if "/" in project:
            return project
        return f"{self.group_path}/{project}"

    # -------------------------------------------------------------------------
    # Normalized wrappers — translate Copa Agent tool args → MCP tool args
    # -------------------------------------------------------------------------

    async def get_file_contents(self, project: str, file_path: str, ref: str = "main") -> dict:
        return await self.call_tool("get_file_contents", {
            "project_id": self._resolve_project_id(project),
            "file_path": file_path,
            "ref": ref,
        })

    async def create_branch(self, project: str, branch: str, ref: str = "main") -> dict:
        result = await self.call_tool("create_branch", {
            "project_id": self._resolve_project_id(project),
            "branch": branch,
            "ref": ref,
        })
        if result.get("ok"):
            result["branch"] = branch
            result["project"] = self._resolve_project_id(project)
        return result

    async def create_or_update_file(self, project: str, file_path: str, content: str,
                                     commit_message: str, branch: str) -> dict:
        result = await self.call_tool("create_or_update_file", {
            "project_id": self._resolve_project_id(project),
            "file_path": file_path,
            "content": content,
            "commit_message": commit_message,
            "branch": branch,
        })
        if result.get("ok"):
            result["file_path"] = file_path
            result["branch"] = branch
        return result

    async def create_merge_request(self, project: str, title: str, source_branch: str,
                                    target_branch: str = "main", description: str = "") -> dict:
        result = await self.call_tool("create_merge_request", {
            "project_id": self._resolve_project_id(project),
            "title": title,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "description": description,
        })
        if result.get("ok"):
            result["project"] = self._resolve_project_id(project)
        return result

    async def create_issue(self, project: str, title: str, description: str = "",
                            labels: list = None) -> dict:
        args = {
            "project_id": self._resolve_project_id(project),
            "title": title,
            "description": description,
        }
        if labels:
            args["labels"] = ",".join(labels)
        result = await self.call_tool("create_issue", args)
        if result.get("ok"):
            result["project"] = self._resolve_project_id(project)
        return result
