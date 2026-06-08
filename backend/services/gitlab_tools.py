"""
Copa Agent — GitLab Tool Executor
==================================

This is the layer the *agent's* tool calls actually execute against. It is the
single source of truth for every action Copa Agent can take on GitLab.

Two execution modes, chosen automatically per-process:

  • LIVE         — a real GITLAB_PERSONAL_ACCESS_TOKEN is present and
                   python-gitlab authenticates successfully. Every tool performs
                   a real GitLab API call (real branches, real MRs, real issues).

  • SIMULATION   — no token / auth failed. Tools run against an in-memory model
                   of the World Cup platform that *behaves* like GitLab: it has a
                   seeded failing pipeline, real job logs, and the planted
                   TOKEN_EXPIRY bug. Creating a branch/MR/issue mutates this
                   state so the agent's multi-step workflow stays internally
                   consistent across a whole demo — and a re-run of the fixed
                   pipeline actually turns green.

Both modes return the *same* structured dict shape, so the agent loop and the
UI never need to care which one is active. That is what makes the demo
bulletproof and the moment-a-token-drops-in upgrade free.
"""

import os
import re
import copy
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("copa-agent.services.gitlab_tools")

try:
    import gitlab  # python-gitlab
    GITLAB_SDK_AVAILABLE = True
except ImportError:
    GITLAB_SDK_AVAILABLE = False
    logger.warning("python-gitlab not installed — GitLab tools will run in SIMULATION mode.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------------
#  SIMULATION WORLD
# ----------------------------------------------------------------------------
# A self-consistent snapshot of the World Cup platform. The planted bug lives in
# worldcup-ticketing-api: TOKEN_EXPIRY_SECONDS = 360 (should be 3600), which
# fails the unit test `test_token_expiry_constant`. The agent reads the real
# job log, patches the real constant, opens an MR — and a re-run goes green.

_TICKETING_FILE_PATH = "app/main.py"

_TICKETING_FILE_BUGGY = '''\
# --- Constants ---
TOKEN_EXPIRY_SECONDS = 360  # BUG: Should be 3600 (1 hour), typo causes tokens to expire in 6 minutes
MAX_TICKETS_PER_USER = 4
TICKET_CATEGORIES = ["Category 1", "Category 2", "Category 3", "Category 4"]
'''

_FAILING_JOB_LOG = """\
$ pytest tests/ -v --tb=short
============================= test session starts ==============================
platform linux -- Python 3.11.6, pytest-7.4.3
collected 8 items

tests/test_auth.py::test_token_expiry_constant FAILED                    [ 12%]
tests/test_auth.py::test_max_tickets_per_user PASSED                     [ 25%]
tests/test_auth.py::test_ticket_categories_exist PASSED                  [ 37%]
tests/test_auth.py::test_generate_auth_token PASSED                      [ 50%]
tests/test_auth.py::test_validate_auth_token_valid PASSED               [ 62%]
tests/test_auth.py::test_validate_auth_token_expired PASSED             [ 75%]
tests/test_auth.py::test_health_endpoint PASSED                          [ 87%]
tests/test_auth.py::test_root_endpoint PASSED                            [100%]

=================================== FAILURES ===================================
_________________________ test_token_expiry_constant ___________________________

    def test_token_expiry_constant():
        from app.main import TOKEN_EXPIRY_SECONDS
>       assert TOKEN_EXPIRY_SECONDS == EXPECTED_TOKEN_EXPIRY, (
            f"Expected token expiry {EXPECTED_TOKEN_EXPIRY}, got {TOKEN_EXPIRY_SECONDS}. "
            f"Tokens expiring too quickly will lock fans out at venue entry gates."
        )
E       AssertionError: Expected token expiry 3600, got 360.
E       Tokens expiring too quickly will lock fans out at venue entry gates.
E       assert 360 == 3600

tests/test_auth.py:19: AssertionError
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_token_expiry_constant - AssertionError: Expec...
ERROR: Job failed: exit code 1
"""


def _fresh_sim_state() -> dict:
    return {
        "projects": {
            "worldcup/worldcup-fan-app": {
                "id": 101,
                "name": "worldcup-fan-app",
                "default_branch": "main",
                "branches": ["main", "develop"],
                "pipelines": [
                    {"id": 78, "status": "success", "ref": "main", "sha": "a1b2c3d", "created_at": _now()},
                ],
                "merge_requests": [],
                "issues": [],
                "files": {},
                "next_mr_iid": 12,
                "next_issue_iid": 6,
            },
            "worldcup/worldcup-ticketing-api": {
                "id": 102,
                "name": "worldcup-ticketing-api",
                "default_branch": "main",
                "branches": ["main"],
                "pipelines": [
                    {"id": 42, "status": "failed", "ref": "main", "sha": "f00dbad",
                     "created_at": _now(),
                     "jobs": [
                         {"name": "build", "stage": "build", "status": "success"},
                         {"name": "unit_test", "stage": "test", "status": "failed", "log": _FAILING_JOB_LOG},
                     ]},
                ],
                "merge_requests": [],
                "issues": [
                    {"iid": 22, "title": "bug: Auth token expiry too short",
                     "state": "opened", "labels": ["bug", "critical"], "created_at": _now()},
                ],
                "files": {_TICKETING_FILE_PATH: _TICKETING_FILE_BUGGY},
                "next_mr_iid": 18,
                "next_issue_iid": 23,
            },
            "worldcup/worldcup-stadium-dashboard": {
                "id": 103,
                "name": "worldcup-stadium-dashboard",
                "default_branch": "main",
                "branches": ["main"],
                "pipelines": [
                    {"id": 31, "status": "running", "ref": "main", "sha": "c0ffee1", "created_at": _now()},
                ],
                "merge_requests": [],
                "issues": [],
                "files": {},
                "next_mr_iid": 7,
                "next_issue_iid": 4,
            },
        }
    }


class GitLabToolExecutor:
    """Executes the concrete GitLab tool calls the agent decides to make."""

    def __init__(self):
        self.token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "")
        self.api_url = os.getenv("GITLAB_API_URL", "https://gitlab.com/api/v4")
        self.group_path = os.getenv("GITLAB_GROUP_PATH", "worldcup")
        self.gl = None
        self.mode = "simulation"
        self._sim = _fresh_sim_state()

        if GITLAB_SDK_AVAILABLE and self.token and not self.token.startswith("glpat-xxxx"):
            try:
                self.gl = gitlab.Gitlab(
                    self.api_url.replace("/api/v4", ""),
                    private_token=self.token,
                )
                self.gl.auth()
                self.mode = "live"
                logger.info("GitLab tool executor: LIVE mode (authenticated).")
            except Exception as e:
                logger.warning(f"GitLab auth failed ({e}); falling back to SIMULATION mode.")
                self.gl = None

        if self.mode == "simulation":
            logger.info("GitLab tool executor: SIMULATION mode (no live token).")

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

    # ========================================================================
    #  TOOL IMPLEMENTATIONS
    #  Each returns a JSON-serializable dict. Same shape in both modes.
    # ========================================================================

    def list_pipelines(self, project: str, limit: int = 5) -> dict:
        path = self._resolve_project_path(project)
        if self.mode == "live":
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
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        return self._ok(project=path, pipelines=[
            {k: v for k, v in p.items() if k != "jobs"} for p in proj["pipelines"][:limit]
        ])

    def list_pipeline_jobs(self, project: str, pipeline_id: int) -> dict:
        path = self._resolve_project_path(project)
        if self.mode == "live":
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
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        pl = next((p for p in proj["pipelines"] if p["id"] == int(pipeline_id)), None)
        if not pl:
            return self._err(f"Pipeline #{pipeline_id} not found in {path}")
        return self._ok(project=path, pipeline_id=pipeline_id, jobs=[
            {"name": j["name"], "stage": j["stage"], "status": j["status"]}
            for j in pl.get("jobs", [])
        ])

    def get_pipeline_job_log(self, project: str, job_name: str, pipeline_id: Optional[int] = None) -> dict:
        path = self._resolve_project_path(project)
        if self.mode == "live":
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
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        for pl in proj["pipelines"]:
            for j in pl.get("jobs", []):
                if j["name"] == job_name and "log" in j:
                    return self._ok(project=path, job_name=job_name, log=j["log"])
        return self._err(f"No log available for job '{job_name}'")

    def get_file_contents(self, project: str, file_path: str, ref: str = "main") -> dict:
        path = self._resolve_project_path(project)
        if self.mode == "live":
            try:
                proj = self.gl.projects.get(path)
                f = proj.files.get(file_path=file_path, ref=ref)
                return self._ok(project=path, file_path=file_path,
                                content=f.decode().decode("utf-8", errors="replace"))
            except Exception as e:
                return self._err(f"get_file_contents failed: {e}")
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        content = proj["files"].get(file_path)
        if content is None:
            return self._err(f"File '{file_path}' not found in {path}")
        return self._ok(project=path, file_path=file_path, content=content)

    def create_branch(self, project: str, branch: str, ref: str = "main") -> dict:
        path = self._resolve_project_path(project)
        if self.mode == "live":
            try:
                proj = self.gl.projects.get(path)
                b = proj.branches.create({"branch": branch, "ref": ref})
                return self._ok(project=path, branch=b.name, web_url=getattr(b, "web_url", ""))
            except Exception as e:
                return self._err(f"create_branch failed: {e}")
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        if branch not in proj["branches"]:
            proj["branches"].append(branch)
        return self._ok(project=path, branch=branch, created_from=ref,
                        web_url=f"https://gitlab.com/{path}/-/tree/{branch}")

    def create_or_update_file(self, project: str, file_path: str, content: str,
                              branch: str, commit_message: str) -> dict:
        path = self._resolve_project_path(project)
        if self.mode == "live":
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
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        proj.setdefault("branch_files", {}).setdefault(branch, {})[file_path] = content
        # Record that this branch now carries a fix (used by re-run-pipeline).
        proj.setdefault("fixed_branches", set())
        if "TOKEN_EXPIRY_SECONDS = 3600" in content:
            proj["fixed_branches"].add(branch)
        return self._ok(project=path, file_path=file_path, branch=branch,
                        commit_message=commit_message)

    def create_merge_request(self, project: str, source_branch: str, title: str,
                             description: str = "", target_branch: str = "main") -> dict:
        path = self._resolve_project_path(project)
        if self.mode == "live":
            try:
                proj = self.gl.projects.get(path)
                mr = proj.mergerequests.create({
                    "source_branch": source_branch, "target_branch": target_branch,
                    "title": title, "description": description,
                })
                return self._ok(project=path, mr_iid=mr.iid, title=mr.title, web_url=mr.web_url)
            except Exception as e:
                return self._err(f"create_merge_request failed: {e}")
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        iid = proj["next_mr_iid"]
        proj["next_mr_iid"] += 1
        mr = {"iid": iid, "title": title, "description": description, "state": "opened",
              "source_branch": source_branch, "target_branch": target_branch,
              "author": "Copa Agent", "created_at": _now(),
              "web_url": f"https://gitlab.com/{path}/-/merge_requests/{iid}"}
        proj["merge_requests"].append(mr)
        return self._ok(project=path, mr_iid=iid, title=title, web_url=mr["web_url"])

    def create_issue(self, project: str, title: str, description: str = "",
                     labels: Optional[list] = None) -> dict:
        path = self._resolve_project_path(project)
        if self.mode == "live":
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
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        iid = proj["next_issue_iid"]
        proj["next_issue_iid"] += 1
        issue = {"iid": iid, "title": title, "description": description,
                 "state": "opened", "labels": labels or [], "created_at": _now(),
                 "web_url": f"https://gitlab.com/{path}/-/issues/{iid}"}
        proj["issues"].append(issue)
        return self._ok(project=path, issue_iid=iid, title=title, web_url=issue["web_url"])

    def run_pipeline(self, project: str, ref: str = "main") -> dict:
        """Trigger a pipeline. In simulation, a branch that carries the fix goes
        green; anything else reproduces the original failure — so the agent can
        *prove* its fix worked."""
        path = self._resolve_project_path(project)
        if self.mode == "live":
            try:
                proj = self.gl.projects.get(path)
                pl = proj.pipelines.create({"ref": ref})
                return self._ok(project=path, pipeline_id=pl.id, status=pl.status,
                                ref=ref, web_url=pl.web_url)
            except Exception as e:
                return self._err(f"run_pipeline failed: {e}")
        proj = self._sim["projects"].get(path)
        if not proj:
            return self._err(f"Unknown project '{path}'")
        fixed = ref in proj.get("fixed_branches", set())
        new_id = max((p["id"] for p in proj["pipelines"]), default=40) + 1
        status = "success" if fixed else ("running" if proj["name"].endswith("dashboard") else "failed")
        proj["pipelines"].insert(0, {"id": new_id, "status": status, "ref": ref,
                                     "sha": "newsha1", "created_at": _now()})
        return self._ok(project=path, pipeline_id=new_id, status=status, ref=ref,
                        web_url=f"https://gitlab.com/{path}/-/pipelines/{new_id}")

    def get_platform_status(self) -> dict:
        """Aggregate latest pipeline status across all World Cup repos."""
        if self.mode == "live":
            try:
                group = self.gl.groups.get(self.group_path)
                rows = []
                for p in group.projects.list(get_all=True):
                    full = self.gl.projects.get(p.id)
                    pls = full.pipelines.list(per_page=1, get_all=False)
                    latest = pls[0].status if pls else "unknown"
                    rows.append({"project": full.path_with_namespace, "status": latest})
                return self._ok(projects=rows)
            except Exception as e:
                return self._err(f"get_platform_status failed: {e}")
        rows = [{"project": path, "status": proj["pipelines"][0]["status"]}
                for path, proj in self._sim["projects"].items()]
        return self._ok(projects=rows)
