"""
Copa Agent — GitLab Webhook Routes
Receives GitLab webhook events and auto-triggers agent triage on failures.
"""

import os
import logging
from fastapi import APIRouter, Request, HTTPException
from routes.agent import agent_svc

logger = logging.getLogger("copa-agent.routes.webhooks")
router = APIRouter()

GITLAB_WEBHOOK_SECRET = os.getenv("GITLAB_WEBHOOK_SECRET", "")


@router.post("/gitlab")
async def gitlab_webhook(request: Request):
    """
    Handle GitLab webhook events.

    Supported events:
    - Pipeline failures → Auto-triage with Copa Agent
    - Merge request events → Notify and summarize
    - Push events → Track deployments
    """
    if GITLAB_WEBHOOK_SECRET:
        token = request.headers.get("X-Gitlab-Token", "")
        if token != GITLAB_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook token")
    try:
        payload = await request.json()
        event_type = payload.get("object_kind", "unknown")
        
        logger.info(f"Received GitLab webhook: {event_type}")
        
        if event_type == "pipeline":
            return await handle_pipeline_event(payload)
        elif event_type == "merge_request":
            return await handle_merge_request_event(payload)
        elif event_type == "push":
            return await handle_push_event(payload)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return {"status": "ignored", "event": event_type}
            
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def handle_pipeline_event(payload: dict):
    """Handle pipeline status change events."""
    status = payload.get("object_attributes", {}).get("status", "unknown")
    pipeline_id = payload.get("object_attributes", {}).get("id")
    project_name = payload.get("project", {}).get("path_with_namespace", "unknown")
    ref = payload.get("object_attributes", {}).get("ref", "unknown")
    
    logger.info(f"Pipeline #{pipeline_id} in {project_name} — status: {status}")
    
    if status == "failed":
        # Auto-trigger Copa Agent to investigate
        message = (
            f"🚨 ALERT: Pipeline #{pipeline_id} just failed in {project_name} "
            f"on branch '{ref}'. Investigate the failure, diagnose the root cause, "
            f"and propose a fix. Follow the Pipeline Triage Workflow."
        )
        
        response = await agent_svc.send_message(
            message=message,
            session_id=f"webhook-{pipeline_id}"
        )
        
        return {
            "status": "triaging",
            "pipeline_id": pipeline_id,
            "project": project_name,
            "agent_response": response["reply"][:200]
        }
    
    return {"status": "noted", "pipeline_id": pipeline_id, "pipeline_status": status}


async def handle_merge_request_event(payload: dict):
    """Handle merge request events."""
    action = payload.get("object_attributes", {}).get("action", "unknown")
    mr_title = payload.get("object_attributes", {}).get("title", "")
    mr_iid = payload.get("object_attributes", {}).get("iid")
    project_name = payload.get("project", {}).get("path_with_namespace", "unknown")
    
    logger.info(f"MR #{mr_iid} in {project_name} — action: {action}, title: {mr_title}")
    
    return {
        "status": "noted",
        "event": "merge_request",
        "action": action,
        "mr_iid": mr_iid,
        "project": project_name
    }


async def handle_push_event(payload: dict):
    """Handle push events (code pushed to repo)."""
    ref = payload.get("ref", "")
    project_name = payload.get("project", {}).get("path_with_namespace", "unknown")
    commits_count = len(payload.get("commits", []))
    
    logger.info(f"Push to {project_name} on {ref} — {commits_count} commits")
    
    return {
        "status": "noted",
        "event": "push",
        "ref": ref,
        "project": project_name,
        "commits": commits_count
    }
