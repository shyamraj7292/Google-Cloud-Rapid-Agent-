"""
Copa Agent Backend — Pydantic Models & Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""
    message: str = Field(..., min_length=1, max_length=4000, description="User message to send to Copa Agent")
    session_id: Optional[str] = Field(None, description="Existing session ID to continue conversation")


class AgentAction(BaseModel):
    """Represents a single action taken by the agent."""
    tool_name: str
    description: str
    timestamp: str
    status: str = "completed"  # completed, failed, pending


class ChatResponse(BaseModel):
    """Response body from the /chat endpoint."""
    reply: str
    session_id: str
    actions: List[AgentAction] = []
    timestamp: str


class PipelineStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    PENDING = "pending"
    CANCELED = "canceled"
    SKIPPED = "skipped"


class PipelineInfo(BaseModel):
    """Pipeline status information."""
    id: int
    project_name: str
    status: PipelineStatus
    ref: str
    sha: str
    web_url: str
    created_at: str
    updated_at: Optional[str] = None


class ProjectInfo(BaseModel):
    """GitLab project summary."""
    id: int
    name: str
    path_with_namespace: str
    web_url: str
    default_branch: str = "main"
    last_pipeline_status: Optional[PipelineStatus] = None


class DashboardData(BaseModel):
    """Aggregated dashboard data."""
    projects: List[ProjectInfo] = []
    pipelines: List[PipelineInfo] = []
    recent_actions: List[AgentAction] = []
    total_pipelines_today: int = 0
    success_rate: float = 0.0


class SessionHistory(BaseModel):
    """Conversation session history."""
    session_id: str
    messages: List[dict] = []
    created_at: str
    updated_at: str


class WebhookPayload(BaseModel):
    """GitLab webhook payload (simplified)."""
    object_kind: str
    object_attributes: dict = {}
    project: dict = {}
    user: dict = {}


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    agent_name: str = "Copa Agent ⚽"
    timestamp: str
