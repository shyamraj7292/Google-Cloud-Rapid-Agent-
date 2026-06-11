"""
Copa Agent — GitLab Tool Executor
==================================

This is the layer the *agent's* tool calls actually execute against. It is the
single source of truth for every action Copa Agent can take on GitLab.

Production mode only — this is a live-data system:

  • A real GITLAB_PERSONAL_ACCESS_TOKEN is required. python-gitlab
    authenticates against the configured GitLab instance and every tool
    performs a real GitLab API call (real pipelines, real branches, real
    MRs, real issues, real wiki pages).

  • If credentials are missing or auth fails, tools return a real error
    (`{"ok": False, "error": "..."}`) — there is no fake/simulated data.
"""

import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("copa-agent.services.gitlab_tools")

try:
    import gitlab  # python-gitlab
    GITLAB_SDK_AVAILABLE = True
except ImportError:
    GITLAB_SDK_AVAILABLE = False
    logger.warning("python-gitlab not installed — GitLab tools will be unavailable.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GitLabToolExecutor:
    """
    Executes the concrete GitLab tool calls the agent decides to make.

    Hybrid MCP + python-gitlab design:
      • Write operations (get_file_contents, create_branch, create_or_update_file,
        create_merge_request, create_issue) are routed through the official GitLab
        MCP server (@modelcontextprotocol/server-gitlab) when available — satisfying
        the hackathon's "Partner Power / MCP integration" requirement.
      • Pipeline operations (list_pipelines, list_pipeline_jobs, get_pipeline_job_log,
        run_pipeline, get_platform_status) are not covered by the official MCP server
        and continue to use python-gitlab directly.
      • If no live credentials are configured, every tool returns a real error.
    """

    def __init__(self):
        self.token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "")
        self.api_url = os.getenv("GITLAB_API_URL", "https://gitlab.com/api/v4")
        self.group_path = os.getenv("GITLAB_GROUP_PATH", "worldcup")
        self.gl = None
        self.mode = "unavailable"
        self.mcp = None  # MCPGitLabClient — set via async init_mcp()

        if not GITLAB_SDK_AVAILABLE:
            logger.error("python-gitlab not installed — GitLab tools are unavailable.")
        elif not self.token or self.token.startswith("glpat-xxxx"):
            logger.error("GITLAB_PERSONAL_ACCESS_TOKEN not set — GitLab tools are unavailable.")
        else:
            try:
                self.gl = gitlab.Gitlab(
                    self.api_url.replace("/api/v4", ""),
                    private_token=self.token,
                )
                self.gl.auth()
                self.mode = "live"
                logger.info("GitLab tool executor: LIVE mode (authenticated).")
            except Exception as e:
                logger.error(f"GitLab auth failed ({e}) — GitLab tools are unavailable.")
                self.gl = None

    async def init_mcp(self):
        """Start the MCP client (called once at app startup from lifespan)."""
        if self.mode != "live":
            return
        try:
            from services.mcp_client import MCPGitLabClient
            self.mcp = MCPGitLabClient(self.token, self.api_url, self.group_path)
            await self.mcp.start()
            if self.mcp.available:
                self.mode = "mcp+live"
                logger.info("GitLab mode: MCP+LIVE (write ops via MCP, pipeline ops via API).")
        except Exception as e:
            logger.warning(f"MCP client init failed: {e} — staying in LIVE mode.")

    async def stop_mcp(self):
        if self.mcp:
            await self.mcp.stop()

    # -- helpers -------------------------------------------------------------
    def _resolve_project_path(self, project: str) -> str:
        """Accept 'worldcup-fan-app' or full 'worldcup/worldcup-fan-app'."""
        if "/" in project:
            return project
        return f"{self.group_path}/{project}"

    def _ok(self, **kw) -> dict:
        return {"ok": True, **kw}

    def _err(self, message: str) -> dict:
        return {"ok": False, "error": message}

    def _unavailable(self, tool: str) -> dict:
        return self._err(
            f"{tool} failed: GitLab is not connected (no live credentials configured)."
        )

    # ========================================================================
    #  TOOL IMPLEMENTATIONS
    #  Each returns a JSON-serializable dict, backed by real GitLab data.
    # ========================================================================

    def list_pipelines(self, project: str, limit: int = 5) -> dict:
        path = self._resolve_project_path(project)
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("list_pipelines")
        try:
            proj = self.gl.projects.get(path)
            pls = proj.pipelines.list(per_page=limit, get_all=False)
            return self._ok(project=path, pipelines=[
                {"id": p.id, "status": p.status, "ref": p.ref,
                 "sha": getattr(p, "sha", "")[:8], "web_url": p.web_url}
                for p in pls
            ])
        except Exception as e:
            return self._err(f"list_pipelines failed: {e}")

    def list_pipeline_jobs(self, project: str, pipeline_id: int) -> dict:
        path = self._resolve_project_path(project)
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("list_pipeline_jobs")
        try:
            proj = self.gl.projects.get(path)
            pl = proj.pipelines.get(pipeline_id)
            jobs = pl.jobs.list(get_all=True)
            return self._ok(project=path, pipeline_id=pipeline_id, jobs=[
                {"id": j.id, "name": j.name, "stage": j.stage, "status": j.status}
                for j in jobs
            ])
        except Exception as e:
            return self._err(f"list_pipeline_jobs failed: {e}")

    def get_pipeline_job_log(self, project: str, job_name: str, pipeline_id: Optional[int] = None) -> dict:
        path = self._resolve_project_path(project)
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("get_pipeline_job_log")
        try:
            proj = self.gl.projects.get(path)
            pl = proj.pipelines.get(pipeline_id) if pipeline_id else proj.pipelines.list(per_page=1)[0]
            job = next((j for j in pl.jobs.list(get_all=True) if j.name == job_name), None)
            if not job:
                return self._err(f"Job '{job_name}' not found")
            full_job = proj.jobs.get(job.id)
            log = full_job.trace().decode("utf-8", errors="replace")
            return self._ok(project=path, job_name=job_name, log=log[-6000:])
        except Exception as e:
            return self._err(f"get_pipeline_job_log failed: {e}")

    async def get_file_contents(self, project: str, file_path: str, ref: str = "main") -> dict:
        path = self._resolve_project_path(project)
        # MCP path — preferred when available
        if self.mcp and self.mcp.available:
            result = await self.mcp.get_file_contents(project, file_path, ref)
            if result.get("ok"):
                # Normalize: MCP returns decoded content in the JSON blob
                content = result.get("content", result.get("result", ""))
                return self._ok(project=path, file_path=file_path, content=content, via="mcp")
        # python-gitlab fallback
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("get_file_contents")
        try:
            proj = self.gl.projects.get(path)
            f = proj.files.get(file_path=file_path, ref=ref)
            return self._ok(project=path, file_path=file_path,
                            content=f.decode().decode("utf-8", errors="replace"))
        except Exception as e:
            return self._err(f"get_file_contents failed: {e}")

    async def create_branch(self, project: str, branch: str, ref: str = "main") -> dict:
        path = self._resolve_project_path(project)
        # MCP path
        if self.mcp and self.mcp.available:
            result = await self.mcp.create_branch(project, branch, ref)
            if result.get("ok"):
                return self._ok(project=path, branch=branch, via="mcp",
                                web_url=f"https://gitlab.com/{path}/-/tree/{branch}")
        # python-gitlab fallback
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("create_branch")
        try:
            proj = self.gl.projects.get(path)
            b = proj.branches.create({"branch": branch, "ref": ref})
            return self._ok(project=path, branch=b.name, web_url=getattr(b, "web_url", ""))
        except Exception as e:
            return self._err(f"create_branch failed: {e}")

    async def create_or_update_file(self, project: str, file_path: str, content: str,
                                     branch: str, commit_message: str) -> dict:
        path = self._resolve_project_path(project)
        # MCP path
        if self.mcp and self.mcp.available:
            result = await self.mcp.create_or_update_file(
                project, file_path, content, commit_message, branch)
            if result.get("ok"):
                return self._ok(project=path, file_path=file_path,
                                branch=branch, commit_message=commit_message, via="mcp")
        # python-gitlab fallback
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("create_or_update_file")
        try:
            proj = self.gl.projects.get(path)
            try:
                f = proj.files.get(file_path=file_path, ref=branch)
                f.content = content
                f.save(branch=branch, commit_message=commit_message)
            except gitlab.exceptions.GitlabGetError:
                proj.files.create({
                    "file_path": file_path, "branch": branch,
                    "content": content, "commit_message": commit_message,
                })
            return self._ok(project=path, file_path=file_path, branch=branch,
                            commit_message=commit_message)
        except Exception as e:
            return self._err(f"create_or_update_file failed: {e}")

    async def create_merge_request(self, project: str, source_branch: str, title: str,
                                    description: str = "", target_branch: str = "main") -> dict:
        path = self._resolve_project_path(project)
        # MCP path
        if self.mcp and self.mcp.available:
            result = await self.mcp.create_merge_request(
                project, title, source_branch, target_branch, description)
            if result.get("ok"):
                iid = result.get("iid", result.get("mr_iid", "?"))
                web_url = result.get("web_url", f"https://gitlab.com/{path}/-/merge_requests/{iid}")
                return self._ok(project=path, mr_iid=iid, title=title,
                                web_url=web_url, via="mcp")
        # python-gitlab fallback
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("create_merge_request")
        try:
            proj = self.gl.projects.get(path)
            mr = proj.mergerequests.create({
                "source_branch": source_branch, "target_branch": target_branch,
                "title": title, "description": description,
            })
            return self._ok(project=path, mr_iid=mr.iid, title=mr.title, web_url=mr.web_url)
        except Exception as e:
            return self._err(f"create_merge_request failed: {e}")

    async def create_issue(self, project: str, title: str, description: str = "",
                            labels: Optional[list] = None) -> dict:
        path = self._resolve_project_path(project)
        # MCP path
        if self.mcp and self.mcp.available:
            result = await self.mcp.create_issue(project, title, description, labels)
            if result.get("ok"):
                iid = result.get("iid", result.get("issue_iid", "?"))
                web_url = result.get("web_url", f"https://gitlab.com/{path}/-/issues/{iid}")
                return self._ok(project=path, issue_iid=iid, title=title,
                                web_url=web_url, via="mcp")
        # python-gitlab fallback
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("create_issue")
        try:
            proj = self.gl.projects.get(path)
            issue = proj.issues.create({
                "title": title, "description": description,
                "labels": ",".join(labels or []),
            })
            return self._ok(project=path, issue_iid=issue.iid, title=issue.title,
                            web_url=issue.web_url)
        except Exception as e:
            return self._err(f"create_issue failed: {e}")

    async def create_wiki_page(self, project: str, title: str, content: str) -> dict:
        """Publish a wiki page (used for incident postmortems). No MCP wiki
        support exists yet, so this goes straight to python-gitlab."""
        path = self._resolve_project_path(project)
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", title.strip().lower()).strip("-") or "postmortem"
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("create_wiki_page")
        try:
            proj = self.gl.projects.get(path)
            page = proj.wikis.create({"title": title, "content": content, "format": "markdown"})
            web_url = f"{self.api_url.replace('/api/v4', '')}/{path}/-/wikis/{getattr(page, 'slug', slug)}"
            return self._ok(project=path, title=title, slug=getattr(page, "slug", slug), web_url=web_url)
        except Exception as e:
            return self._err(f"create_wiki_page failed: {e}")

    def run_pipeline(self, project: str, ref: str = "main") -> dict:
        """Trigger a real pipeline run via the GitLab API."""
        path = self._resolve_project_path(project)
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("run_pipeline")
        try:
            proj = self.gl.projects.get(path)
            pl = proj.pipelines.create({"ref": ref})
            return self._ok(project=path, pipeline_id=pl.id, status=pl.status,
                            ref=ref, web_url=pl.web_url)
        except Exception as e:
            return self._err(f"run_pipeline failed: {e}")

    def _list_world_cup_projects(self) -> list:
        """Return path_with_namespace for every project in the configured group
        (or owned-project namespace fallback for personal accounts)."""
        try:
            group = self.gl.groups.get(self.group_path)
            return [p.path_with_namespace for p in group.projects.list(get_all=True)]
        except Exception:
            all_projects = self.gl.projects.list(owned=True, get_all=True)
            return [p.path_with_namespace for p in all_projects
                    if p.namespace.get("path", "") == self.group_path]

    def get_stadium_traffic(self, stadium: str = "MetLife Stadium") -> dict:
        """Match Day Simulator: real-time platform load signal derived from live
        GitLab CI/CD activity. Counts pipelines created in the last 15 minutes
        across every World Cup project — a burst of pipeline/deploy activity is
        treated as a load surge the agent should react to. No synthetic numbers."""
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("get_stadium_traffic")
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
            recent = []
            for path in self._list_world_cup_projects():
                proj = self.gl.projects.get(path)
                for pl in proj.pipelines.list(per_page=10, get_all=False):
                    created = datetime.fromisoformat(pl.created_at.replace("Z", "+00:00"))
                    if created >= cutoff:
                        recent.append({"project": path, "status": pl.status, "created_at": pl.created_at})
            active = len(recent)
            surge = active >= 2
            affected = recent[0]["project"].split("/")[-1] if recent else None
            return self._ok(
                stadium=stadium,
                recent_pipeline_runs=active,
                window_minutes=15,
                surge=surge,
                affected_service=affected if surge else None,
            )
        except Exception as e:
            return self._err(f"get_stadium_traffic failed: {e}")

    async def scale_service(self, project: str, replicas: int) -> dict:
        """Scale a service by committing an updated replica count to its
        deployment config (k8s/deployment.yaml) on the project's default
        branch — a real, auditable GitLab commit. No in-memory fake state."""
        path = self._resolve_project_path(project)
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("scale_service")
        try:
            proj = self.gl.projects.get(path)
            file_path = "k8s/deployment.yaml"
            branch = proj.default_branch
            previous = None
            try:
                f = proj.files.get(file_path=file_path, ref=branch)
                content = f.decode().decode("utf-8", errors="replace")
                m = re.search(r"replicas:\s*(\d+)", content)
                if m:
                    previous = int(m.group(1))
                    new_content = re.sub(r"replicas:\s*\d+", f"replicas: {replicas}", content, count=1)
                else:
                    new_content = content.rstrip("\n") + f"\nreplicas: {replicas}\n"
                f.content = new_content
                f.save(branch=branch,
                       commit_message=f"chore: scale {path} to {replicas} replicas (Match Day Simulator)")
            except gitlab.exceptions.GitlabGetError:
                new_content = f"# Match Day Simulator scaling config\nreplicas: {replicas}\n"
                proj.files.create({
                    "file_path": file_path, "branch": branch,
                    "content": new_content,
                    "commit_message": f"chore: scale {path} to {replicas} replicas (Match Day Simulator)",
                })
            return self._ok(project=path, previous_replicas=previous, replicas=replicas,
                            file_path=file_path, branch=branch)
        except Exception as e:
            return self._err(f"scale_service failed: {e}")

    def get_platform_status(self) -> dict:
        """Aggregate latest pipeline status across all World Cup repos."""
        if self.mode not in ("live", "mcp+live") or not self.gl:
            return self._unavailable("get_platform_status")
        try:
            rows = []
            for path in self._list_world_cup_projects():
                full = self.gl.projects.get(path)
                pls = full.pipelines.list(per_page=1, get_all=False)
                latest = pls[0].status if pls else "unknown"
                rows.append({"project": full.path_with_namespace, "status": latest,
                             "web_url": full.web_url})
            return self._ok(projects=rows)
        except Exception as e:
            return self._err(f"get_platform_status failed: {e}")
