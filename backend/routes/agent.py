"""
Copa Agent — Agent Interaction Routes
Handles chat sessions with the Agent Builder agent.
"""

import os
import uuid
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from services.agent_service import AgentService
from services.memory_service import MemoryService

logger = logging.getLogger("copa-agent.routes.agent")
router = APIRouter()

agent_svc = AgentService()
memory_svc = MemoryService()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ActionItem(BaseModel):
    tool: str
    description: str
    status: str  # "running", "completed", "failed"
    result: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    actions: List[ActionItem]
    timestamp: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to Copa Agent and receive a response with actions taken.
    The agent will use GitLab MCP tools to take real actions.
    """
    try:
        # Create or continue session
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(f"[Session {session_id}] User: {request.message[:100]}...")
        
        # Save user message to memory
        await memory_svc.save_message(session_id, "user", request.message)
        
        # Get conversation history for context
        history = await memory_svc.get_history(session_id)
        
        # Send to Agent Builder
        response = await agent_svc.send_message(
            message=request.message,
            session_id=session_id,
            history=history
        )
        
        # Save agent response to memory
        await memory_svc.save_message(session_id, "assistant", response["reply"])
        
        logger.info(f"[Session {session_id}] Agent: {response['reply'][:100]}...")
        logger.info(f"[Session {session_id}] Actions taken: {len(response['actions'])}")
        
        return ChatResponse(
            reply=response["reply"],
            session_id=session_id,
            actions=[ActionItem(**a) for a in response["actions"]],
            timestamp=response["timestamp"]
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """Get the conversation history for a specific session."""
    try:
        history = await memory_svc.get_history(session_id)
        return {"session_id": session_id, "messages": history}
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    try:
        await memory_svc.clear_session(session_id)
        return {"message": f"Session {session_id} cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
