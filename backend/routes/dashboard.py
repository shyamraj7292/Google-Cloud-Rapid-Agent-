"""
Copa Agent — Dashboard Data Routes
Provides pipeline status, project info, and deployment data for the frontend.
"""

import logging
from fastapi import APIRouter, HTTPException
from services.gitlab_service import GitLabService

logger = logging.getLogger("copa-agent.routes.dashboard")
router = APIRouter()

gitlab_svc = GitLabService()


@router.get("/projects")
async def list_projects():
    """Get all World Cup GitLab projects with their latest pipeline status."""
    try:
        projects = await gitlab_svc.get_worldcup_projects()
        return {"projects": projects}
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pipelines")
async def get_project_pipelines(project_id: str, limit: int = 10):
    """Get recent pipelines for a specific project."""
    try:
        pipelines = await gitlab_svc.get_pipelines(project_id, limit)
        return {"project_id": project_id, "pipelines": pipelines}
    except Exception as e:
        logger.error(f"Error fetching pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/merge-requests")
async def get_project_merge_requests(project_id: str, state: str = "opened"):
    """Get merge requests for a specific project."""
    try:
        mrs = await gitlab_svc.get_merge_requests(project_id, state)
        return {"project_id": project_id, "merge_requests": mrs}
    except Exception as e:
        logger.error(f"Error fetching merge requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/issues")
async def get_project_issues(project_id: str, state: str = "opened"):
    """Get issues for a specific project."""
    try:
        issues = await gitlab_svc.get_issues(project_id, state)
        return {"project_id": project_id, "issues": issues}
    except Exception as e:
        logger.error(f"Error fetching issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def platform_status():
    """Get overall World Cup platform status — aggregates all repos."""
    try:
        status = await gitlab_svc.get_platform_status()
        return status
    except Exception as e:
        logger.error(f"Error fetching platform status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/venues")
async def get_venues():
    """Get all World Cup 2026 venues with deployment status."""
    venues = [
        {"id": 1, "name": "MetLife Stadium", "city": "East Rutherford, NJ", "country": "USA", "lat": 40.8128, "lng": -74.0742, "status": "deployed"},
        {"id": 2, "name": "AT&T Stadium", "city": "Arlington, TX", "country": "USA", "lat": 32.7473, "lng": -97.0945, "status": "deployed"},
        {"id": 3, "name": "SoFi Stadium", "city": "Inglewood, CA", "country": "USA", "lat": 33.9535, "lng": -118.3392, "status": "staging"},
        {"id": 4, "name": "Hard Rock Stadium", "city": "Miami Gardens, FL", "country": "USA", "lat": 25.9580, "lng": -80.2389, "status": "deployed"},
        {"id": 5, "name": "Lumen Field", "city": "Seattle, WA", "country": "USA", "lat": 47.5952, "lng": -122.3316, "status": "deployed"},
        {"id": 6, "name": "Gillette Stadium", "city": "Foxborough, MA", "country": "USA", "lat": 42.0909, "lng": -71.2643, "status": "staging"},
        {"id": 7, "name": "Lincoln Financial Field", "city": "Philadelphia, PA", "country": "USA", "lat": 39.9008, "lng": -75.1675, "status": "deployed"},
        {"id": 8, "name": "Mercedes-Benz Stadium", "city": "Atlanta, GA", "country": "USA", "lat": 33.7554, "lng": -84.4010, "status": "deployed"},
        {"id": 9, "name": "NRG Stadium", "city": "Houston, TX", "country": "USA", "lat": 29.6847, "lng": -95.4107, "status": "pending"},
        {"id": 10, "name": "Arrowhead Stadium", "city": "Kansas City, MO", "country": "USA", "lat": 39.0489, "lng": -94.4839, "status": "deployed"},
        {"id": 11, "name": "BMO Field", "city": "Toronto, ON", "country": "Canada", "lat": 43.6332, "lng": -79.4186, "status": "deployed"},
        {"id": 12, "name": "BC Place", "city": "Vancouver, BC", "country": "Canada", "lat": 49.2768, "lng": -123.1118, "status": "staging"},
        {"id": 13, "name": "Estadio Azteca", "city": "Mexico City", "country": "Mexico", "lat": 19.3029, "lng": -99.1505, "status": "deployed"},
        {"id": 14, "name": "Estadio BBVA", "city": "Monterrey", "country": "Mexico", "lat": 25.6699, "lng": -100.2461, "status": "deployed"},
        {"id": 15, "name": "Estadio Akron", "city": "Guadalajara", "country": "Mexico", "lat": 20.6810, "lng": -103.4625, "status": "pending"},
        {"id": 16, "name": "Levi's Stadium", "city": "Santa Clara, CA", "country": "USA", "lat": 37.4033, "lng": -121.9694, "status": "deployed"},
    ]
    return {"venues": venues}
