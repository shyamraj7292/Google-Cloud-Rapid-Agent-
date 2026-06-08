"""
Copa Agent — Agent Interaction Routes
Handles chat sessions with the Agent Builder agent.
"""

import os
import json
import uuid
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream the agent's reason→act→observe loop as Server-Sent Events.

    Emits one SSE `data:` line per event:
      {type: "status", text}            — a short "thinking" line
      {type: "action", tool, description, status, result}  — a tool just ran
      {type: "reply",  reply}           — the final assistant message
      {type: "done"}                    — stream complete

    This is what lets the UI show Copa Agent *working*, step by step, live.
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator():
        # Tell the client its session id up front.
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        await memory_svc.save_message(session_id, "user", request.message)
        final_reply = ""
        try:
            async for ev in agent_svc.run_stream(request.message, session_id):
                if ev.get("type") == "reply":
                    final_reply = ev.get("reply", "")
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'reply', 'reply': f'⚠️ Agent error: {e}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        if final_reply:
            await memory_svc.save_message(session_id, "assistant", final_reply)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/mode")
async def agent_mode():
    """Expose which backend + GitLab mode is active (shown as a badge in the UI)."""
    return {
        "agent_backend": agent_svc.mode,
        "gitlab_mode": agent_svc.tools.mode,
        "model": agent_svc.model_name,
    }


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
