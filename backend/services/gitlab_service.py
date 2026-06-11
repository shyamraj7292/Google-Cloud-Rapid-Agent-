"""
Copa Agent — GitLab Service
Direct GitLab API integration for dashboard data and quick queries.
"""

import os
import logging
from typing import Optional, List

logger = logging.getLogger("copa-agent.services.gitlab")

# Try to import python-gitlab
try:
    import gitlab
    GITLAB_AVAILABLE = True
except ImportError:
    GITLAB_AVAILABLE = False
    logger.warning("python-gitlab not installed. Using mock GitLab data.")


class GitLabService:
    """
    Service for direct GitLab API calls (used by the dashboard for real-time data).
    """
    
    def __init__(self):
        self.token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "")
        self.api_url = os.getenv("GITLAB_API_URL", "https://gitlab.com")
        self.group_path = os.getenv("GITLAB_GROUP_PATH", "")
        self.gl = None
        
        if GITLAB_AVAILABLE and self.token:
            try:
                self.gl = gitlab.Gitlab(
                    self.api_url.replace("/api/v4", ""),
                    private_token=self.token
                )
                self.gl.auth()
                logger.info("GitLab client authenticated successfully")
            except Exception as e:
                logger.warning(f"GitLab authentication failed: {e}. Using mock data.")
                self.gl = None
    
    async def get_worldcup_projects(self) -> List[dict]:
        """Get all World Cup projects with latest pipeline status."""
        if self.gl and self.group_path:
            try:
                # Support user namespaces (not just groups)
                try:
                    ns = self.gl.groups.get(self.group_path)
                    raw_projects = ns.projects.list(get_all=True)
                    project_ids = [p.id for p in raw_projects]
                except Exception:
                    all_owned = self.gl.projects.list(owned=True, get_all=True)
                    project_ids = [p.id for p in all_owned
                                   if p.namespace.get("path", "") == self.group_path]

                result = []
                for pid in project_ids:
                    try:
                        full_proj = self.gl.projects.get(pid)
                        pipelines = full_proj.pipelines.list(per_page=1)
                        latest_pipeline = None
                        if pipelines:
                            p = pipelines[0]
                            latest_pipeline = {
                                "id": p.id,
                                "status": p.status,
                                "ref": p.ref,
                                "created_at": p.created_at,
                                "web_url": p.web_url
                            }
                        # Last 5 pipeline statuses for sparkline
                        history = []
                        for p in full_proj.pipelines.list(per_page=5):
                            history.append(p.status)

                        open_mrs = len(full_proj.mergerequests.list(state="opened", per_page=5, get_all=False))
                        open_issues = len(full_proj.issues.list(state="opened", per_page=5, get_all=False))

                        result.append({
                            "id": full_proj.id,
                            "name": full_proj.name,
                            "path": full_proj.path_with_namespace,
                            "web_url": full_proj.web_url,
                            "description": getattr(full_proj, "description", "") or "",
                            "latest_pipeline": latest_pipeline,
                            "pipeline_history": history,
                            "open_mrs": open_mrs,
                            "open_issues": open_issues,
                        })
                    except Exception as e:
                        logger.warning(f"Skipping project {pid}: {e}")

                return result
            except Exception as e:
                logger.error(f"Error fetching GitLab projects: {e}")
        
        # Mock data for development
        return [
            {
                "id": 1,
                "name": "worldcup-fan-app",
                "path": "worldcup/worldcup-fan-app",
                "web_url": "https://gitlab.com/worldcup/worldcup-fan-app",
                "latest_pipeline": {"id": 78, "status": "success", "ref": "main", "created_at": "2026-06-08T08:30:00Z", "web_url": "#"},
                "open_mrs": 2,
                "open_issues": 5
            },
            {
                "id": 2,
                "name": "worldcup-ticketing-api",
                "path": "worldcup/worldcup-ticketing-api",
                "web_url": "https://gitlab.com/worldcup/worldcup-ticketing-api",
                "latest_pipeline": {"id": 42, "status": "failed", "ref": "main", "created_at": "2026-06-08T09:15:00Z", "web_url": "#"},
                "open_mrs": 1,
                "open_issues": 3
            },
            {
                "id": 3,
                "name": "worldcup-stadium-dashboard",
                "path": "worldcup/worldcup-stadium-dashboard",
                "web_url": "https://gitlab.com/worldcup/worldcup-stadium-dashboard",
                "latest_pipeline": {"id": 31, "status": "running", "ref": "main", "created_at": "2026-06-08T09:45:00Z", "web_url": "#"},
                "open_mrs": 0,
                "open_issues": 2
            }
        ]
    
    async def get_pipelines(self, project_id: str, limit: int = 10) -> List[dict]:
        """Get recent pipelines for a project."""
        if self.gl:
            try:
                project = self.gl.projects.get(project_id)
                pipelines = project.pipelines.list(per_page=limit)
                return [
                    {
                        "id": p.id,
                        "status": p.status,
                        "ref": p.ref,
                        "created_at": p.created_at,
                        "updated_at": p.updated_at,
                        "web_url": p.web_url,
                        "duration": getattr(p, 'duration', None)
                    }
                    for p in pipelines
                ]
            except Exception as e:
                logger.error(f"Error fetching pipelines: {e}")
        
        return [
            {"id": 42, "status": "failed", "ref": "main", "created_at": "2026-06-08T09:15:00Z", "duration": 145},
            {"id": 41, "status": "success", "ref": "develop", "created_at": "2026-06-08T08:00:00Z", "duration": 132},
            {"id": 40, "status": "success", "ref": "main", "created_at": "2026-06-07T16:30:00Z", "duration": 128},
        ]
    
    async def get_merge_requests(self, project_id: str, state: str = "opened") -> List[dict]:
        """Get merge requests for a project."""
        if self.gl:
            try:
                project = self.gl.projects.get(project_id)
                mrs = project.mergerequests.list(state=state, per_page=20)
                return [
                    {
                        "iid": mr.iid,
                        "title": mr.title,
                        "state": mr.state,
                        "author": mr.author.get("name", "Unknown"),
                        "source_branch": mr.source_branch,
                        "target_branch": mr.target_branch,
                        "created_at": mr.created_at,
                        "web_url": mr.web_url
                    }
                    for mr in mrs
                ]
            except Exception as e:
                logger.error(f"Error fetching MRs: {e}")
        
        return [
            {"iid": 17, "title": "Fix: Auth token expiry typo (360→3600)", "state": "opened", "author": "Copa Agent", "source_branch": "fix/auth-token-expiry", "target_branch": "main", "created_at": "2026-06-08T10:00:00Z", "web_url": "#"},
        ]
    
    async def get_issues(self, project_id: str, state: str = "opened") -> List[dict]:
        """Get issues for a project."""
        if self.gl:
            try:
                project = self.gl.projects.get(project_id)
                issues = project.issues.list(state=state, per_page=20)
                return [
                    {
                        "iid": issue.iid,
                        "title": issue.title,
                        "state": issue.state,
                        "labels": issue.labels,
                        "created_at": issue.created_at,
                        "web_url": issue.web_url
                    }
                    for issue in issues
                ]
            except Exception as e:
                logger.error(f"Error fetching issues: {e}")
        
        return [
            {"iid": 23, "title": "feat: Add Spanish (es) language support", "state": "opened", "labels": ["enhancement", "i18n"], "created_at": "2026-06-08T10:05:00Z", "web_url": "#"},
            {"iid": 22, "title": "bug: Auth token expiry too short", "state": "opened", "labels": ["bug", "critical"], "created_at": "2026-06-08T09:30:00Z", "web_url": "#"},
        ]
    
    async def get_platform_status(self) -> dict:
        """Get aggregated platform health status."""
        projects = await self.get_worldcup_projects()
        
        total = len(projects)
        healthy = sum(1 for p in projects if p.get("latest_pipeline", {}).get("status") == "success")
        failing = sum(1 for p in projects if p.get("latest_pipeline", {}).get("status") == "failed")
        running = sum(1 for p in projects if p.get("latest_pipeline", {}).get("status") == "running")
        
        return {
            "total_projects": total,
            "healthy": healthy,
            "failing": failing,
            "running": running,
            "health_percentage": round((healthy / total) * 100, 1) if total > 0 else 0,
            "projects": projects
        }
