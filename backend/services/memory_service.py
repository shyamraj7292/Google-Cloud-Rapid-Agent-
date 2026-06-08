"""
Copa Agent — Memory Service
Manages conversation history using Firestore or local in-memory fallback.
"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
from collections import defaultdict

logger = logging.getLogger("copa-agent.services.memory")

# Try to import Firestore
try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    logger.warning("Firestore SDK not available. Using in-memory storage.")


class MemoryService:
    """
    Persistent conversation memory service.
    Uses Firestore in production, falls back to in-memory dict for development.
    """
    
    def __init__(self):
        self.collection_name = os.getenv("FIRESTORE_COLLECTION", "copa_agent_sessions")
        self.db = None
        self.local_store = defaultdict(list)
        
        if FIRESTORE_AVAILABLE and os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                self.db = firestore.Client()
                logger.info("Firestore memory service initialized")
            except Exception as e:
                logger.warning(f"Firestore initialization failed: {e}. Using local memory.")
    
    async def save_message(self, session_id: str, role: str, content: str):
        """Save a message to the conversation history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if self.db:
            try:
                doc_ref = self.db.collection(self.collection_name).document(session_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    messages = doc.to_dict().get("messages", [])
                    messages.append(message)
                    doc_ref.update({"messages": messages, "updated_at": message["timestamp"]})
                else:
                    doc_ref.set({
                        "messages": [message],
                        "created_at": message["timestamp"],
                        "updated_at": message["timestamp"]
                    })
                return
            except Exception as e:
                logger.error(f"Firestore save error: {e}")
        
        # Local fallback
        self.local_store[session_id].append(message)
    
    async def get_history(self, session_id: str, limit: int = 20) -> List[dict]:
        """Get conversation history for a session."""
        if self.db:
            try:
                doc_ref = self.db.collection(self.collection_name).document(session_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    messages = doc.to_dict().get("messages", [])
                    return messages[-limit:]
                return []
            except Exception as e:
                logger.error(f"Firestore read error: {e}")
        
        # Local fallback
        return self.local_store.get(session_id, [])[-limit:]
    
    async def clear_session(self, session_id: str):
        """Clear all messages for a session."""
        if self.db:
            try:
                self.db.collection(self.collection_name).document(session_id).delete()
                return
            except Exception as e:
                logger.error(f"Firestore delete error: {e}")
        
        # Local fallback
        if session_id in self.local_store:
            del self.local_store[session_id]
    
    async def list_sessions(self) -> List[dict]:
        """List all active sessions."""
        if self.db:
            try:
                docs = self.db.collection(self.collection_name).stream()
                return [
                    {
                        "session_id": doc.id,
                        "message_count": len(doc.to_dict().get("messages", [])),
                        "updated_at": doc.to_dict().get("updated_at")
                    }
                    for doc in docs
                ]
            except Exception as e:
                logger.error(f"Firestore list error: {e}")
        
        # Local fallback
        return [
            {
                "session_id": sid,
                "message_count": len(msgs),
                "updated_at": msgs[-1]["timestamp"] if msgs else None
            }
            for sid, msgs in self.local_store.items()
        ]
